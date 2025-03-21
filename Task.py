import pathlib


class TaskT():
  def __init__(self, 
        checksum:str,
        filename:str,
        crop:str|None,
        rescales:list[str]|None,
        output_directory:pathlib.Path,
        output_fileformats:list[str],
    ):
    self.image_md5sum = checksum
    self.output_filename = filename
    self.output_directory = output_directory
    self.output_fileformats = output_fileformats
    self.rescales = rescales
    self.crop = crop
    self.image_preprocess = [] # scaled and/or cropped
    self.expected_outputs = []
    
    assert(filename.endswith('_RGB'))
    assert(output_directory.exists())
    return


# TODO: compare the numerical values and ensure uniqueness
def ParseScales(rescales:list[str]) -> list[str]:
    results = []
    for scale in rescales:
      isPercent = scale.endswith('%')
      isMultiplier = scale.endswith('x')
      isValid = (isPercent or isMultiplier)
      
      scalestr = scale.removesuffix('x').removesuffix('%')
      
      if isPercent:
        isValid = scalestr.isdigit()
        if (isValid and (int(scalestr) <= 0)): isValid = False;
        if (isValid and (int(scalestr) == 100)): results.append(''); continue;
      
      if isMultiplier:
        isValid = (
          (scalestr.count('.') <= 1) and
          (scalestr.replace('.','').isdigit())
        )
        if isValid:
          if (float(scalestr) <= 0.0): isValid = False
          if (isValid and (float(scalestr) == 1.0)): results.append(''); continue;
          scalestr = f"{scalestr}x"
      
      if isValid: results.append(f"_scale{scalestr}")
      else: print(f"error: invalid scale: {scale}");
    
    return results


def FillExpectedOutputs(task:TaskT) -> list[str]:
    rescales = task.rescales
    filename = task.output_filename
    output_directory = task.output_directory
    output_fileformats = task.output_fileformats
    
    task.expected_outputs.clear()
    if (rescales is None): rescales = ['100%'];
    for scalestr in ParseScales(rescales):
      for fmt in output_fileformats:
        new_name = f"{filename}{scalestr}.{fmt}"
        final_destination = output_directory/new_name
        
        renamelimit = 10; renamecount=1
        while(final_destination.exists() and (renamecount < renamelimit)):
            print(f"[WARNING] final destination already exists: '{final_destination.absolute()}'")
            new_name = f"{new_name.removesuffix(f'.{fmt}').removesuffix(f'_{renamecount-1}')}_{renamecount}.{fmt}"
            final_destination = output_directory/new_name
            print(f"    renaming: '{final_destination.absolute()}'")
            renamecount += 1
        if renamecount >= renamelimit: print(f"hit rename limit. exiting."); exit(3);
        assert(final_destination.parent.exists());
        assert(final_destination.parent.absolute() == output_directory.absolute());
        print(f"final destination: '{final_destination.absolute()}'")
        task.expected_outputs.append(final_destination)
    print(f"expected outputs: {'\n  '.join(str(x.name) for x in sorted(task.expected_outputs))}")
    return task.expected_outputs


def CheckExpectedOutputs(task:TaskT, work_dir:pathlib.Path) -> list[tuple[pathlib.Path,pathlib.Path]]:
    results = []
    for final_dest in task.expected_outputs:
        work_file = work_dir / final_dest.name
        print(f"checking: {work_file}")
        if work_file.exists(): results.append((work_file, final_dest));
        else: print(f"[WARNING] expected output does not exist! ({work_file})");
    return results
