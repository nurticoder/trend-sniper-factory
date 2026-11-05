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

The bundled v0.1 demonstration uses no external game footage, artwork, logos, textures, characters, music or downloaded stock. Game names and the official game URL are descriptive references, not a grant to use game assets or an affiliation claim. Current production adapters record creator, source URL, exact license and permission evidence for each accepted external asset before rendering. Attribution alone is not permission.

A `TSF_FONT` override is the user's responsibility: use a font with explicit permitted video/commercial use. Do not load random downloaded fonts and assume the Pillow license covers them.

## Optional control-room dependencies

FastAPI and Pydantic use MIT licenses; Uvicorn and Starlette use BSD-3-Clause licenses. Test-only HTTPX2 uses its installed upstream license (copied in `docs/licenses/httpx2-LICENSE.txt`). Direct dependency license texts are included in `docs/licenses/`. These packages are installed separately by pip; this repository does not vendor their source or executables. Transitive dependencies keep their own notices. The dashboard uses system fonts and original CSS/SVG assets; it loads no external font or CDN.

The optional YouTube publisher installs Google's API client and OAuth helper separately through pip. Their upstream licenses are preserved in `docs/licenses/`. The online material collector uses the Wikimedia Commons API. Each accepted file retains a separate rights record and credit in the local production manifest. The repository distributes no Commons or user-library media.

## Optional local narration

Current production uses creator-selected **Kokoro-82M v1.0**, `af_heart`. Model weights are [Apache-2.0](https://huggingface.co/hexgrad/Kokoro-82M); the separately installed [kokoro-onnx 0.4.7 runner](https://github.com/thewh1teagle/kokoro-onnx) is MIT. `soundfile` retains its BSD license and underlying native-library notices. Runtime/transitive dependencies are installed by pip and are not redistributed here. Explicit setup downloads the upstream int8 ONNX and voice bank, records their source URLs/licenses and verifies pinned hashes. These binaries and generated audio remain outside Git. The production voice is not cloned from a reference creator.

Piper is retained only as an explicit legacy audition/setup utility, with its earlier notices below. It is not an automatic fallback from Kokoro.

Piper TTS 1.8.0 is separately installed from [PyPI](https://pypi.org/project/piper-tts/1.8.0/) and run as a child command-line process. Its engine is GPL-3.0-or-later, with additional bundled component notices. [Engine source at v1.8.0](https://github.com/OHF-Voice/piper1-gpl/tree/v1.8.0) and installed notices are retained in `docs/licenses/piper-*`. The repository does not redistribute the engine, native libraries or models. Packaging those into a future installer/container requires the applicable dependency/source obligations to be handled separately.

The legacy Piper model installer retrieves only `en_US-ljspeech-medium` at revision `e7229f7d33a10e145e109b886d661984201ac3c4` of [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices/tree/e7229f7d33a10e145e109b886d661984201ac3c4/en/en_US/ljspeech/medium). The repository declares MIT for the model; this voice's exact model card identifies the LJ Speech training dataset as public domain. [LJ Speech's publisher](https://keithito.com/LJ-Speech-Dataset/) specifies public-domain status in the US. These are separate model, dataset and engine records, not a blanket license for other voices.

Model, configuration and model-card hashes are pinned and checked before synthesis. Downloads stay under ignored `local-data/voices/`, with the model card and a provenance receipt. Every voiced preview records the exact model/config/card digests, spoken text, measured utterance timing and narration-audio digest. No reference creator's voice is extracted or cloned.
