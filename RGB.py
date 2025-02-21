import pathlib


def HueRotate(base_img:pathlib.Path, rotation_interval:int):
    hue_shifts = [*[x for x in range(100,300,rotation_interval)], 300]
    hue_rotation_commands = [
        f"gm convert {base_img.name} -modulate 100,100,{str(x).zfill(3)} hueshift/{str(x).zfill(3)}{base_img.suffix}"
        for x in hue_shifts
    ]
    morph_command = f"gm convert hueshift/*{base_img.suffix} -morph {rotation_interval} -monitor {base_img.stem}_RGB.gif"
    return (hue_rotation_commands, morph_command)


def SaveCommands(cmdlist:list[str]):
    cmdfile = pathlib.Path.cwd() / "rgb_cmdlist.bash"
    with cmdfile.open(mode='w', encoding="utf-8") as newfile:
        newfile.write('\n'.join(cmdlist))
        newfile.write('\n')


# TODO: handle transparency in input!!
# TODO: transcode input image to PNG and downscale if necessary
# TODO: frames generated for GIF output need preprocessing to reduced (255) color-palette

# TODO: handle GIF/video inputs (divide into frames and interpolate between them)


if __name__ == "__main__":
    cwd = pathlib.Path.cwd()
    img = cwd / "imgName.png"
    assert(img.exists())
    
    
    hue_rotation_commands = [
      f'convert {img.stem}.png -modulate 100,100,000 hueshift/000.png',
      f'convert {img.stem}.png -modulate 100,100,010 hueshift/010.png',
      f'convert {img.stem}.png -modulate 100,100,020 hueshift/020.png',
      f'convert {img.stem}.png -modulate 100,100,030 hueshift/030.png',
      f'convert {img.stem}.png -modulate 100,100,040 hueshift/040.png',
      f'convert {img.stem}.png -modulate 100,100,050 hueshift/050.png',
      f'convert {img.stem}.png -modulate 100,100,060 hueshift/060.png',
      f'convert {img.stem}.png -modulate 100,100,070 hueshift/070.png',
      f'convert {img.stem}.png -modulate 100,100,080 hueshift/080.png',
      f'convert {img.stem}.png -modulate 100,100,090 hueshift/090.png',
      f'convert {img.stem}.png -modulate 100,100,100 hueshift/100.png',
      f'convert {img.stem}.png -modulate 100,100,110 hueshift/110.png',
      f'convert {img.stem}.png -modulate 100,100,120 hueshift/120.png',
      f'convert {img.stem}.png -modulate 100,100,130 hueshift/130.png',
      f'convert {img.stem}.png -modulate 100,100,140 hueshift/140.png',
      f'convert {img.stem}.png -modulate 100,100,150 hueshift/150.png',
      f'convert {img.stem}.png -modulate 100,100,160 hueshift/160.png',
      f'convert {img.stem}.png -modulate 100,100,170 hueshift/170.png',
      f'convert {img.stem}.png -modulate 100,100,180 hueshift/180.png',
      f'convert {img.stem}.png -modulate 100,100,190 hueshift/190.png',
      f'convert {img.stem}.png -modulate 100,100,200 hueshift/200.png',
    ]
    morph_command = f'convert hueshift/*.png -morph 10 -monitor {img.stem}_RGB.gif'
    all_hueshift_cmd = '\n'.join(hue_rotation_commands)+'\n\n'

