RBGifier
--------

| your image                                   | RGBified                                             |
|----------------------------------------------|------------------------------------------------------|
| ![colorchart](/readme_assets/colorchart.png) | ![colorchart_RGB](/readme_assets/colorchart_RGB.mp4) |


### usage
run 'CLI.py', providing stepsize and an image \
output will be written into the same directory as the original image \
CLI.py --help

On startup, the script looks for 'main_config.json' under the 'configs_RGBifier' directory. \
An empty config will be created if none exists.
See the [example config](/configs_RGBifier/main_config.example.json) for keys/values


### prerequisites
requires [ImageMagick]() and/or [GraphicsMagick]() (select with '--magick' arg) \
MP4 output requires ffmpeg

