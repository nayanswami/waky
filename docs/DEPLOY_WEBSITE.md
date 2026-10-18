# Deploying the Waky website to Netlify

The site is plain static HTML in `website/` (no build step). `netlify.toml` already sets `publish = "website"` plus security headers.

## 1. Host the installer
Netlify rejects single files over 100 MB and the installer is larger, so host it on GitHub Releases:

1. Build: `scripts\build_windows.ps1` (needs Inno Setup 6) -> `dist\installer\Waky-Setup-<version>.exe`
2. Create a GitHub release and attach the installer.
3. Copy the direct asset link and paste it into `website/site-config.js` as `downloadUrl`.

Until `downloadUrl` is set, every Download button shows "The installer is not published yet".

## 2. Deploy
- Drag the `website` folder onto https://app.netlify.com/drop, or
- Connect the repo in Netlify (build command empty, publish directory `website`).

## 3. Preview locally
```bash
cd website && python -m http.server 8765
```
Open http://127.0.0.1:8765.

## Edit points
- Download link, version, size: `website/site-config.js`
- Demo scenarios (what the hero types out): top of `website/main.js`
- Colours and fonts: CSS variables at the top of `website/styles.css`
