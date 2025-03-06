the Environment-Variable controlling where ImageMagick and GraphicsMagick look for configs is: "MAGICK_CONFIGURE_PATH"
export MAGICK_CONFIGURE_PATH="../RGBifier/magick_configs/"

the default search paths are:
    /usr/share/GraphicsMagick-1.3.42/config/
    /usr/lib/GraphicsMagick-1.3.42/config/
    /etc/ImageMagick-6/
you can find the default/global config files there.

GraphicsMagick searches for hardcoded filenames with '.mgk' file-extension; log.mgk, delegates.mgk, type.mgk, etc.
ImageMagick does the same, except it's config files use '.xml' extension.
you can see it search for the configs on startup when 'MAGICK_DEBUG' contains 'Configure'

ImageMagick loads all configs from all search paths, not just the first.
You can see this with 'identify -list Policy'
you may need to copy the .xml files here into "~/.config/ImageMagick/",
so that your configs are loaded both before and after all system/default configs.

'.mgk' files are just XML files.
make sure there's a space between the start and end of any comments '<-- x -->'; otherwise it breaks.

more info about config files:
https://imagemagick.org/script/resources.php#configure
http://www.graphicsmagick.org/GraphicsMagick.html#file

