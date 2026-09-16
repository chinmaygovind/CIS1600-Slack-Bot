# Deployment bits that live on the box

These are **not** applied by any deploy step; they are hand-installed over SSH
and kept here so a rebuilt box can be put back the way it was.

## `systemd/cis1600-ed.service.d/override.conf`

A drop-in for `cis1600-ed.service`, needed once the Ed module started attaching
homework pages. The base unit runs the bot with `ProtectHome=read-only` and only
opens `logs/` for writing, and caps the service at 128M -- neither of which the
homework build can live within. Install with:

```bash
sudo mkdir -p /etc/systemd/system/cis1600-ed.service.d
sudo cp deploy/systemd/cis1600-ed.service.d/override.conf \
        /etc/systemd/system/cis1600-ed.service.d/
sudo systemctl daemon-reload && sudo systemctl restart cis1600-ed
```

The box also needs the LaTeX toolchain, installed without recommends to keep it
to ~450 MB:

```bash
sudo apt-get install -y --no-install-recommends \
    texlive-latex-extra texlive-plain-generic lmodern latexmk poppler-utils
```

Building the LuaTeX formats gets OOM-killed on a 951 MB box, and nothing here
needs them, so they are disabled:

```bash
for f in dvilualatex lualatex luahbtex luatex luajittex; do
    sudo fmtutil-sys --disablefmt $f
done
sudo dpkg --configure -a
```
