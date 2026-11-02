# Third-party notices

The project source is MIT. This does not relicense dependencies, game trademarks or any assets you add.

| Component | License / origin | Handling |
| --- | --- | --- |
| Pillow 13.0.0 | MIT-CMU; https://github.com/python-pillow/Pillow | Installed separately by pip. License copied to `docs/licenses/pillow-LICENSE.txt`. |
| imageio-ffmpeg 0.8.0 wrapper | BSD-2-Clause; https://github.com/imageio/imageio-ffmpeg | Installed separately by pip. License copied to `docs/licenses/imageio-ffmpeg-LICENSE.txt`. |
| FFmpeg executable | LGPL-2.1+ base; enabled GPL components change license; https://ffmpeg.org/legal.html | Dependency wheels may include GPL FFmpeg. The tested ARM build enables GPL and libx264. No FFmpeg executable is copied into this repository or source ZIP. |
| Aileron Regular subset | Sora Sagano; Pillow's bundled default scalable font, upstream https://dotcolon.net/font/aileron/ | Used through Pillow, not extracted or redistributed as a font file. Upstream Aileron is released under CC0; commercial rendered text is permitted. |
| Python | PSF; https://docs.python.org/3/license.html | User-installed runtime. |

The installed FFmpeg build configuration is saved beside every rendered video in `ffmpeg-version.txt`. Running a separate GPL encoder executable does not change the license of this project's independent Python source or grant rights to input media. If redistributing dependencies, Docker images, installers or executables, separately satisfy their license/source obligations for the exact builds. Consult the wrapper's upstream build scripts and FFmpeg source, rather than treating the wrapper's BSD license as the encoder license. This release ships only our source, dependency notices and rendered demonstration media.

No game footage, artwork, logos, textures, characters, music or downloaded stock is used. Game names and the official game URL are descriptive references, not a grant to use game assets or an affiliation claim. The renderer does not accept external assets in v0.1. Any later asset adapter must record creator, source URL, exact license and permission evidence in the manifest before rendering. Attribution alone is not permission.

A `TSF_FONT` override is the user's responsibility: use a font with explicit permitted video/commercial use. Do not load random downloaded fonts and assume the Pillow license covers them.

## Optional control-room dependencies

FastAPI and Pydantic use MIT licenses; Uvicorn and Starlette use BSD-3-Clause licenses. Test-only HTTPX2 uses its installed upstream license (copied in `docs/licenses/httpx2-LICENSE.txt`). Direct dependency license texts are included in `docs/licenses/`. These packages are installed separately by pip; this repository does not vendor their source or executables. Transitive dependencies keep their own notices. The dashboard uses system fonts and original CSS/SVG assets; it loads no external font or CDN.
