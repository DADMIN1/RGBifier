RBGifier
--------

| your image                                    | RGBified                                      |
|-----------------------------------------------|-----------------------------------------------|
| !["your image"](readme_assets/colorchart.png) | !["RGBified"](readme_assets/rgb_scale75.webp) |


### usage
run 'CLI.py', providing stepsize and an image \
output will be written into the same directory as the original image \
CLI.py --help

On startup, the script looks for 'main_config.json' under the 'configs_RGBifier' directory. \
run 'Config.py' to create/reset config files.
See the [example config](/configs_RGBifier/main_config.example.json) for keys/values


### prerequisites
requires [ImageMagick](https://github.com/ImageMagick/ImageMagick6) and/or [GraphicsMagick](http://www.GraphicsMagick.org/) (select with '--magick' arg) \
MP4 output requires ffmpeg

