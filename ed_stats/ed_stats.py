import os
import sys
import json
from datetime import datetime
from collections import defaultdict, Counter

import requests
import pandas as pd
from dateutil import parser as date_parser
from tqdm import tqdm

# Use the project's EdAPI client (assumed available)
from edapi import EdAPI

HERE = os.path.dirname(__file__)
OUTPUT_DIR = os.path.join(HERE, "output")
TEMPLATE_PATH = os.path.join(HERE, "templates", "dashboard_template.html")

# ----- Configuration constants (edit these) -----
# Set `API_BASE` to your ED API base URL (e.g. "https://ed.example.org/api")
API_BASE = "https://edstem.org/us/courses/"  # e.g. "https://ed.example.org/api"
# Set `TOKEN` to your API token or set the `ED_API_TOKEN` environment variable
TOKEN = "kqiYr0.LBIPE6GTMHQxfNwO1LB7DzvL94SkJgu3GVAYr6w6"
# Course identifier to fetch posts from 
COURSE_ID = "82168"
# Optional: path to a sample JSON file for offline testing
SAMPLE_JSON = None  # e.g. "../sample_posts.json"
# Output directory for generated dashboard
OUT_DIR = OUTPUT_DIR
# -----------------------------------------------

# Debugging / verbose output
DEBUG = True  # set False to silence detailed debug dumps
DEBUG_SAVE_DIR = os.path.join(OUT_DIR, "debug")

import logging
logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO, format='[ed_stats] %(levelname)s: %(message)s')
logger = logging.getLogger("ed_stats")

def _debug_save(name, obj):
    try:
        os.makedirs(DEBUG_SAVE_DIR, exist_ok=True)
        path = os.path.join(DEBUG_SAVE_DIR, f"{name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, default=str, indent=2)
        logger.debug(f"Wrote debug sample to {path}")
    except Exception as e:
        logger.error(f"Failed to write debug sample {name}: {e}")


# Configuration is now provided via the module-level constants above.
def load_config():
    """Return the configuration values from constants.

    This keeps a small compatibility shim for existing callers.
    Edit the constants at the top of this file to configure behaviour.
    """
    token = TOKEN or os.getenv("ED_API_TOKEN")
    return API_BASE, token, COURSE_ID, SAMPLE_JSON, OUT_DIR


def fetch_posts(api_base, token, course_id):
    """
    Fetch posts/questions for the given course. This function assumes the API exposes
    an endpoint like: GET {api_base}/courses/{course_id}/posts

    The function is intentionally small and will raise informative errors if the
    API shape is different; adapt the endpoint URL formatting as needed for your ED
    installation.
    """
    # Use EdAPI client to list threads (consistent with modules/ed_module.py)
    ed = EdAPI()
    threads = ed.list_threads(course_id=int(course_id), limit=1000, sort="new")
    return threads


def fetch_replies(api_base, token, post_id):
    # Use EdAPI client to fetch thread details and extract replies
    ed = EdAPI()
    thread = ed.get_thread(int(post_id))
    for key in ("replies", "comments", "posts", "responses", "answers"):
        if key in thread and isinstance(thread[key], list):
            return thread[key]
    return []


def parse_posts(raw_posts):
    """Normalize posts JSON into a pandas DataFrame with keys we need."""
    rows = []
    for p in tqdm(raw_posts, desc="Parsing posts", unit="post"):
        # The structure will vary. We support a few common shapes.
        post_id = p.get("id") or p.get("post_id")
        title = p.get("title") or p.get("subject") or p.get("text", "(no title)")
        author = p.get("author", {}).get("name") if isinstance(p.get("author"), dict) else p.get("author")
        created = p.get("created_at") or p.get("created") or p.get("timestamp")
        created_dt = None
        try:
            # Handle numeric epoch timestamps (ms or s)
            if isinstance(created, (int, float)):
                # treat > 10**12 as microseconds? commonly ED uses milliseconds
                ts = float(created)
                if ts > 1e12:
                    # milliseconds
                    created_dt = datetime.fromtimestamp(ts / 1000.0)
                else:
                    created_dt = datetime.fromtimestamp(ts)
            elif isinstance(created, str) and created.isdigit():
                ts = float(created)
                if ts > 1e12:
                    created_dt = datetime.fromtimestamp(ts / 1000.0)
                else:
                    created_dt = datetime.fromtimestamp(ts)
            else:
                created_dt = date_parser.parse(created) if created else None
        except Exception:
            created_dt = None
        # If we cannot parse a created timestamp, raise an error so user can inspect raw data
        if created is not None and created_dt is None:
            msg = f"Failed to parse 'created' for post id={post_id!r}. raw created value={created!r}. full post={json.dumps(p, default=str)}"
            logger.error(msg)
            raise ValueError(msg)
        rows.append({
            "post_id": post_id,
            "title": title,
            "author": author,
            "created": created_dt,
            "raw": p,
        })
    return pd.DataFrame(rows)


def compute_metrics(posts_df, replies_map, course_id=None):
    """Compute response times and leaderboards.

    replies_map: dict post_id -> list of reply dicts (should include author and created_at)
    """
    data = []
    staff_response_times = defaultdict(list)
    staff_counts = Counter()
    # EdAPI client and user cache for resolving user ids to names
    ed_client = EdAPI()
    user_cache = {}
    # authenticate EdAPI if supported
    try:
        if hasattr(ed_client, 'login'):
            try:
                ed_client.login()
                logger.debug("EdAPI: logged in successfully")
            except Exception as e:
                logger.debug(f"EdAPI login failed or not required: {e}")
    except Exception:
        logger.debug("EdAPI login call failed or not present")

    # Prefetch course users mapping (id -> name) using EdAPI.list_users
    try:
        if course_id is not None:
            try:
                course_users = ed_client.list_users(course_id=int(course_id))
            except Exception:
                course_users = ed_client.list_users(course_id=course_id)
        else:
            course_users = []
        for u in course_users or []:
            if not isinstance(u, dict):
                continue
            uid = u.get('id') or u.get('user_id') or u.get('userId') or u.get('uid')
            name = u.get('name') or u.get('display_name') or u.get('full_name') or u.get('real_name') or u.get('username')
            if uid and name:
                user_cache[str(uid)] = name
        logger.debug(f"Prefetched {len(user_cache)} users for course {course_id}")
    except Exception as e:
        logger.debug(f"Could not prefetch course users via EdAPI.list_users: {e}")

    for _, row in tqdm(posts_df.iterrows(), total=len(posts_df), desc="Computing metrics", unit="post"):
        post_id = row["post_id"]
        created = row["created"]
        # ensure created is a datetime (handle numbers/strings)
        if isinstance(created, (int, float)):
            ts = float(created)
            created = datetime.fromtimestamp(ts / 1000.0) if ts > 1e12 else datetime.fromtimestamp(ts)
        # if pandas Timestamp
        try:
            if hasattr(created, 'to_pydatetime'):
                created = created.to_pydatetime()
        except Exception:
            pass
        replies = replies_map.get(str(post_id)) or replies_map.get(post_id) or []
        # Find first staff reply (we treat any reply with `is_staff` True or author != OP as staff)
        first_staff_reply = None
        # sort replies by created time, robustly extracting timestamps
        def reply_ts_key(x):
            val = x.get("created_at") or x.get("created") or x.get("timestamp") or x.get("createdAt")
            if isinstance(val, (int, float)):
                return val
            if isinstance(val, str) and val.isdigit():
                return float(val)
            return str(val or "")

        # Pre-parse reply timestamps and validate authors; raise if badly formed
        parsed_any = False
        parsed_replies = []
        for r in replies:
            r_created = r.get("created_at") or r.get("created") or r.get("timestamp") or r.get("createdAt")
            # Resolve author: author may be dict, string, or a user id under user_id/userId/user
            r_author = None
            raw_author = r.get("author")
            if isinstance(raw_author, dict):
                r_author = raw_author.get("name") or raw_author.get("display_name") or raw_author.get("full_name")
            elif isinstance(raw_author, str):
                r_author = raw_author
            # try user id fields
            if not r_author:
                uid = r.get("user_id") or r.get("userId") or r.get("user")
                if isinstance(uid, dict):
                    r_author = uid.get("name") or uid.get("display_name")
                elif uid:
                    # lookup via cache or EdAPI
                    if uid in user_cache:
                        r_author = user_cache[uid]
                    else:
                        try:
                            # Try a sequence of likely EdAPI methods to resolve a user id
                            lookup = None
                            tried = []
                            for fn in ("get_user", "get_user_info", "get_user_by_id", "get_user_by", "get_user_profile", "get_user_profile_by_id", "user", "get_users", "list_users", "users", "list_users"):
                                if hasattr(ed_client, fn):
                                    tried.append(fn)
                                    try:
                                        candidate = getattr(ed_client, fn)
                                        res = candidate(int(uid)) if isinstance(uid, (int, float)) or (isinstance(uid, str) and uid.isdigit()) else candidate(uid)
                                    except TypeError:
                                        # maybe expects no args or different signature
                                        try:
                                            res = candidate()
                                        except Exception:
                                            res = None
                                    except Exception:
                                        res = None
                                    if res:
                                        lookup = res
                                        break

                            # If a list of users was returned, try to find the user by id or username
                            name = None
                            if isinstance(lookup, dict):
                                name = lookup.get("name") or lookup.get("display_name") or lookup.get("full_name") or lookup.get("real_name") or lookup.get("username")
                            elif isinstance(lookup, list):
                                for u in lookup:
                                    if not isinstance(u, dict):
                                        continue
                                    if str(u.get("id")) == str(uid) or str(u.get("user_id")) == str(uid) or str(u.get("username")) == str(uid):
                                        name = u.get("name") or u.get("display_name") or u.get("full_name") or u.get("real_name") or u.get("username")
                                        break

                            if name:
                                r_author = name
                            elif lookup is not None:
                                # fallback to stringifying whatever we got
                                try:
                                    if isinstance(lookup, dict):
                                        r_author = str(lookup.get("id") or lookup.get("username") or lookup)
                                    else:
                                        r_author = str(lookup)
                                except Exception:
                                    r_author = str(uid)
                            else:
                                logger.debug(f"Could not fetch user {uid} via EdAPI; tried methods: {tried}")
                                r_author = str(uid)
                            user_cache[uid] = r_author
                        except Exception as e:
                            logger.debug(f"Could not fetch user {uid} via EdAPI: {e}")
                            r_author = str(uid)
            # check author present
            if r_author is None:
                msg = f"Reply missing author for post {post_id}. reply={json.dumps(r, default=str)}"
                logger.error(msg)
                raise ValueError(msg)
            # try parse
            r_dt = None
            try:
                if isinstance(r_created, (int, float)):
                    ts = float(r_created)
                    r_dt = datetime.fromtimestamp(ts / 1000.0) if ts > 1e12 else datetime.fromtimestamp(ts)
                elif isinstance(r_created, str) and r_created.isdigit():
                    ts = float(r_created)
                    r_dt = datetime.fromtimestamp(ts / 1000.0) if ts > 1e12 else datetime.fromtimestamp(ts)
                else:
                    r_dt = date_parser.parse(r_created) if r_created else None
            except Exception:
                r_dt = None
            parsed_replies.append((r, r_author, r_created, r_dt))
            if r_dt:
                parsed_any = True

        if len(replies) > 0 and not parsed_any:
            msg = f"No replies for post {post_id} had a parseable timestamp. replies sample={json.dumps(replies[:5], default=str)}"
            logger.error(msg)
            raise ValueError(msg)

        for r, r_author, r_created, r_dt in sorted(parsed_replies, key=lambda x: x[2] if isinstance(x[2], (int, float)) or (isinstance(x[2], str) and x[2].isdigit()) else str(x[2] or "")):
            r_author = r.get("author", {}).get("name") if isinstance(r.get("author"), dict) else r.get("author")
            r_created = r.get("created_at") or r.get("created") or r.get("timestamp")
            # r_dt already parsed above (from parsed_replies)
            # keep r_dt variable in-scope
            if r_dt and created and r_dt >= created:
                # detect staff via several possible flags in ED API
                author_obj = r.get("author") if isinstance(r.get("author"), dict) else {}
                role = author_obj.get("role") or author_obj.get("type") or r.get("author_type")
                is_staff_flag = r.get("is_staff") or r.get("is_instructor") or r.get("is_ta") or r.get("staff")
                is_staff = bool(is_staff_flag) or (role and str(role).lower() in ("staff", "instructor", "ta", "teacher")) or (r_author and r_author != row.get("author"))
                if is_staff:
                    first_staff_reply = (r_author, r_dt)
                    break
        response_seconds = None
        responder = None
        if first_staff_reply and created:
            responder, r_dt = first_staff_reply
            response_seconds = (r_dt - created).total_seconds()
            if responder:
                staff_response_times[responder].append(response_seconds)
                staff_counts[responder] += 1

        data.append({
            "post_id": post_id,
            "title": row.get("title"),
            "created": created,
            "first_responder": responder,
            "response_seconds": response_seconds,
            "num_replies": len(replies),
        })

    stats_df = pd.DataFrame(data)
    # Leaderboard: staff_counts
    leaderboard = pd.DataFrame([{"staff": k, "responses": v} for k, v in staff_counts.items()])
    if not leaderboard.empty:
        leaderboard = leaderboard.sort_values("responses", ascending=False)

    # Average response times per staff
    avg_response = []
    for staff, times in staff_response_times.items():
        avg_response.append({"staff": staff, "avg_response_mins": sum(times) / len(times) / 60.0, "count": len(times)})
    avg_df = pd.DataFrame(avg_response)
    if not avg_df.empty:
        avg_df = avg_df.sort_values("avg_response_mins")

    overall_avg = stats_df["response_seconds"].dropna().mean() if "response_seconds" in stats_df.columns else None

    return {
        "per_post": stats_df,
        "leaderboard": leaderboard,
        "avg_response": avg_df,
        "overall_avg_seconds": overall_avg,
    }


def render_dashboard(metrics, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    # Prepare JSON data to embed
    # Serialize DataFrames manually so we can control datetime formatting and types
    per_post = []
    for _, r in metrics["per_post"].iterrows():
        created = r.get("created")
        if hasattr(created, 'isoformat'):
            created_ser = created.isoformat()
        else:
            # pandas may store timestamps as numpy datetime64 or epoch ms
            try:
                if pd.isna(created):
                    created_ser = None
                else:
                    created_ser = str(created)
            except Exception:
                created_ser = str(created)
        per_post.append({
            "post_id": r.get("post_id"),
            "title": r.get("title"),
            "created": created_ser,
            "first_responder": r.get("first_responder"),
            "response_seconds": float(r.get("response_seconds")) if r.get("response_seconds") is not None else None,
            "num_replies": int(r.get("num_replies") or 0),
        })

    leaderboard = []
    if not metrics["leaderboard"].empty:
        for _, r in metrics["leaderboard"].iterrows():
            leaderboard.append({"staff": r.get("staff"), "responses": int(r.get("responses"))})

    avg_response = []
    if not metrics["avg_response"].empty:
        for _, r in metrics["avg_response"].iterrows():
            avg_response.append({"staff": r.get("staff"), "avg_response_mins": float(r.get("avg_response_mins")), "count": int(r.get("count"))})

    payload = {
        "per_post": per_post,
        "leaderboard": leaderboard,
        "avg_response": avg_response,
        "overall_avg_seconds": metrics["overall_avg_seconds"],
    }

    # Read template
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    out_html = template.replace("__DATA_PAYLOAD__", json.dumps(payload))
    out_path = os.path.join(out_dir, "dashboard.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(out_html)
    print(f"Dashboard generated: {out_path}")


def main():
    api_base, token, course_id, sample_json, out_dir = load_config()

    if sample_json:
        with open(sample_json, "r", encoding="utf-8") as f:
            raw_posts = json.load(f)
    else:
        if not (api_base and token and course_id):
            print("Please set the API_BASE, TOKEN (or ED_API_TOKEN), and COURSE_ID constants at the top of ed_stats/ed_stats.py, or set SAMPLE_JSON for offline testing.")
            sys.exit(2)
        raw_posts = fetch_posts(api_base, token, course_id)

    posts_df = parse_posts(raw_posts)

    # For each post fetch replies
    replies_map = {}
    for pid in tqdm(posts_df["post_id"].dropna().astype(str), desc="Fetching replies", unit="post"):
        try:
            if sample_json:
                # try to find replies embedded in sample JSON
                replies_map[pid] = []
            else:
                replies_map[pid] = fetch_replies(api_base, token, pid)
        except Exception as e:
            print(f"Warning: could not fetch replies for post {pid}: {e}")
            replies_map[pid] = []

    metrics = compute_metrics(posts_df, replies_map, course_id)

    render_dashboard(metrics, out_dir)


if __name__ == "__main__":
    main()
