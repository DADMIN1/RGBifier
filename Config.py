import pathlib
import json

import Globals


CONFIG_DIRNAME = "configs_RGBifier"
CONFIG_DIR:pathlib.Path|None = None


config_entries = { "NAME": str, "ENV_DEFAULTS": dict, "CMDLINE_ARGS": list, "DEBUG_FLAGS": list, }
default_config = { K:T() for (K,T) in config_entries.items() }
example_config = {
    # name of config file.
    "NAME": "main_config.example",
    # note: avoid calling (pathlib) '_.with_suffix(".json")'; it deletes '.backup' and '.example' from filenames
    
    # these values are set if var is not already defined in env
    "ENV_DEFAULTS": {
        "MAGICK_DEBUG": "All",
        "MAGICK_ACCESS_MONITOR": True,
    },
    
    # keyword arguments only
    "CMDLINE_ARGS": [
        "--tmpfs",
        "--noclean",
    ],
    
    # names corresponding to the 'DEBUG_' variables in 'Globals.py' - "PRINT_ONLY", "PARSE_ONLY" etc.
    "DEBUG_FLAGS": [ *Globals.debug_flag_names ],
}


def LoadConfig(config_name:str|None = None, config_dir:pathlib.Path|None = None) -> (bool, dict):
    """Looks for 'main_config.json' if name isn't provided.
    :return: flag indicating success/failure and loaded data."""
    config = {"NAME":(config_name.removesuffix('.json').strip() if config_name else None)}
    if (config_dir is None): config_dir = CONFIG_DIR; assert(CONFIG_DIR is not None);
    if (not config_dir.exists()): return (False, config); # this may return with "NAME":None
    if (name_was_unspecified := ((config_name is None) or (len(config_name.strip()) == 0))):
        print(f"no config-name specified. loading 'main_config'")
        config["NAME"] = config_name = "main_config"
    
    config_path = (config_dir/f"{config_name}.json")
    if (not config_path.exists()):
        if (not name_was_unspecified): print(f"[ERROR] config not found: '{config_path}'"); exit(5);
        return (True, config) # not a problem if defaulted config_name was not found
    print(f"loading config ({config_name}): '{config_path}'")
    
    with config_path.open(mode='r', encoding='utf-8') as config_file:
        config = json.load(config_file)
        config["NAME"] = config_name
    
    # TODO: validate loaded config here
    print(f"loaded config: '{config_name}'")
    return (True, config)


def WriteConfig(config:dict, filename:str|None=None, backup_old:bool=True) -> pathlib.Path|None:
    """reads config['NAME'] for filename by default."""
    assert(CONFIG_DIR.exists() and CONFIG_DIR.is_dir());
    
    filename = (None if ((filename is None) or (len(filename.strip()) == 0)) else filename.strip())
    config_name = (filename.removesuffix('.json') if (filename is not None) else config.get("NAME", None))
    
    if config_name is None: print(f"[ERROR]: cannot save config without filename!!"); return None;
    if (config.get("NAME", '').strip() == ''):
        print(f'[WARNING] config has empty "NAME"! using filename: "{config_name}"')
        config['NAME'] = config_name.removesuffix('.json')
    
    pwd = Globals.PROGRAM_DIR.parent
    config_path = (CONFIG_DIR / f"{config_name}.json").expanduser().absolute()
    print(f"saving config: [{config_name}] -> {config_path.relative_to(pwd)}")
    
    if ((config_path.exists()) and backup_old):
        print(f"config exists! ({config_name})- moving existing config-file to backup")
        backup_path = (CONFIG_DIR/f"{config_name}.backup.json").expanduser().absolute()
        print(f"[old] '{config_path.relative_to(pwd)}' ---> '{backup_path.relative_to(pwd)}' [backup]")
        config_path.replace(backup_path) # moves file, does not alter the current 'config_path'
    else:
        if config_path.exists(): print(f"[WARNING] overwriting existing config");
        print(f"[config] '{config_name}' ---> '{config_path.relative_to(pwd)}'")
    
    with config_path.open(mode='w', encoding='utf-8') as config_file:
        json.dump(config, config_file, indent=2)
    
    print(f"saved config: '{config_path}'")
    return config_path


def ApplyConfig(config:dict) -> (bool, tuple):
    """ :return: flag indicating success/failure and parsed variables """
    success = True; config_name = config.pop("NAME", None) # pop for 'unrecognized_entries' below
    print(f"parsing config: '{config_name}'"); print(f"{'_'*120}\n")
    print(json.dumps(config, indent=2))
    print(f"\n{'_'*120}\n")
    
    unrecognized_entries = [K for K in config.keys() if (K not in config_entries.keys())]
    
    if (len(unrecognized_entries) > 0):
        success = False; print(f"[WARNING] unrecognized entries in config!")
        for entry in unrecognized_entries:
            print(f"  unrecognized entry: '{entry}'")
        print(f"error applying config: '{config_name}'")
    
    cmdline_args = config.get("CMDLINE_ARGS", [])
    env_defaults = config.get("ENV_DEFAULTS", {})
    debug_flags  = config.get("DEBUG_FLAGS",  [])
    
    try: Globals.ApplyDebugFlags(debug_flags);
    except NameError as FAIL: success = False; print(FAIL);
    return (success, (cmdline_args, env_defaults))


def WriteDefaultConfigs(overwrite_existing = False):
    assert(CONFIG_DIR.exists() and CONFIG_DIR.is_dir());
    default_config_files = { 
        "main_config": default_config.copy(),
        "empty_config": default_config.copy(),
        "main_config.example": example_config.copy(),
    }
    
    anyMissing = False; reason = "overwriting" if overwrite_existing else "missing"
    announcement = f"searching: '{CONFIG_DIR.name}' for {reason} default-configs\n"
    
    for (conf_name, config) in default_config_files.items():
        config_path = CONFIG_DIR / f"{conf_name}.json"
        if ((not config_path.exists()) or overwrite_existing):
            if (not anyMissing): print(announcement); anyMissing = True;
            reason = ("MISSING" if (not config_path.exists()) else "OVERWRITING")
            STR = f"{name if (name := config.get('NAME', '')) else 'empty_config'}"
            print(f"{reason}: '{config_path.name}' [{STR}]")
            WriteConfig(config, config_path.name); print('')
    
    if anyMissing: print("finished writing default-configs.\n")
    return


def Init(write_default_configs = True, overwrite_existing = False):
    global CONFIG_DIR; CONFIG_DIR = Globals.PROGRAM_DIR / CONFIG_DIRNAME
    if not CONFIG_DIR.exists(): print(f"new config directory: '{CONFIG_DIR}'"); CONFIG_DIR.mkdir();
    assert(CONFIG_DIR.exists() and CONFIG_DIR.is_dir());
    
    if write_default_configs: WriteDefaultConfigs(overwrite_existing);
    
    (conf_load_success, config) = LoadConfig()
    if not conf_load_success: print(f"[ERROR] config_dir does not exist"); exit(6);
    
    (conf_apply_success, (conf_cmdline_args, conf_env_defaults)) = ApplyConfig(config)
    if not conf_apply_success: print(f"[ERROR] failed to apply config"); exit(7);
    
    return (conf_cmdline_args, conf_env_defaults)
