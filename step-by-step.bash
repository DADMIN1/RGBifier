export MAGICK_DEBUG="All"
export MAGICK_CONFIGURE_PATH="RGBifier/magick_configs/"
export OMP_NUM_THREADS=24
export MAGICK_LIMIT_FILES=8192
export MAGICK_THREAD_LIMIT=$OMP_NUM_THREADS
export MAGICK_FILE_LIMIT=$MAGICK_LIMIT_FILES
ulimit -S -n 8320

# setup environment vars; cd into workdir
# assuming input image is: colorchart.png

# takes 1 parameter; SRCIMG
function SETUP_SCRIPTS()
{
    local SRCIMG=$(realpath "${1}")
    if [[ -f "${SRCIMG}" ]] then echo "srcimg: '${SRCIMG}'";
    else echo "no such file: '${SRCIMG}'"; return; fi;
    
    local ROTATIONS=({300..100..-1})
    local RESCALE_PERCENTS=(10 20 25 30 50 75 100)
    echo "RESCALE_PERCENTS=(${RESCALE_PERCENTS[@]})"; echo "";
    
    local SRCIMG_SCRIPT="preprocess_srcimg.txt"
    if [[ -f "${SRCIMG_SCRIPT}" ]] then 
        echo "script exists: '${SRCIMG_SCRIPT}' - moving to backup";
        mv --verbose "${SRCIMG_SCRIPT}" "backup_${SRCIMG_SCRIPT}"
    fi;
    
    local FINAL_SCRIPT="concat_framegen_script.bash"
    if [[ -f "${FINAL_SCRIPT}" ]] then
        echo "script exists: '${FINAL_SCRIPT}' - moving to backup";
        mv --verbose "${FINAL_SCRIPT}" "backup_${FINAL_SCRIPT}"
    fi;
    
    echo '#!/bin/bash' >> "${FINAL_SCRIPT}"
    echo "function PRINTCMDS() {" >> "${FINAL_SCRIPT}"
    echo "cat ${SRCIMG_SCRIPT}; echo '';" >> "${FINAL_SCRIPT}"
    
    for SS in ${RESCALE_PERCENTS[@]}; do
        local OUTPUT_DIR="frames_scale${SS}"
        
        if [[ -d "${OUTPUT_DIR}" ]] then echo "output dir exists: '${OUTPUT_DIR}' - skipping"; #continue;
        else mkdir --verbose "${OUTPUT_DIR}"; fi;
        
        local BATCHFILE="framegen_cmds_scale${SS}.txt";
        if [[ -f "${BATCHFILE}" ]] then echo "batchfile exists: '${BATCHFILE}' - skipping"; continue; fi;
        
        # replacing the suffix of '.png'
        local SCALED_SRCIMG=${SRCIMG/%'.png'/"_scale${SS}.miff"}
        echo convert-im6.q16 "'PNG:${SRCIMG}'" -strip -crop 2314x2276+0+0 -scale "${SS}%" "'MIFF:${SCALED_SRCIMG}'" >> "${SRCIMG_SCRIPT}"
        
        for index in ${!ROTATIONS[@]}; do
            printf "convert-im6.q16 'MIFF:${SCALED_SRCIMG}' -scene %03d -modulate 100,100,%03d 'MIFF:${OUTPUT_DIR}/frame%03d.miff'\n" ${index} ${ROTATIONS[$index]} ${index} >> "${BATCHFILE}";
        done;
        
        echo "" >> "${BATCHFILE}"
        echo "cat ${BATCHFILE}" >> "${FINAL_SCRIPT}"
    done;
    
    echo "}" >> "${FINAL_SCRIPT}"
    echo "" >> "${FINAL_SCRIPT}"
    echo "" >> "${SRCIMG_SCRIPT}"
    
    echo ""; echo "setup complete. creating combined 'framegen_all' script"
    echo "source '${FINAL_SCRIPT}'; PRINTCMDS > framegen_all.txt"
    source "${FINAL_SCRIPT}"; PRINTCMDS > framegen_all.txt
}

SETUP_SCRIPTS colorchart.png
# mkdir 'frames_scale...'

# setup complete. creating combined 'framegen_all' script
source 'concat_framegen_script.bash'; PRINTCMDS > framegen_all.txt

# then you have to copy-paste all the lines in 'framegen_all'
# trying to pipe or 'cat' it doesn't work for some reason. (quoting handled differently??)

# the first part of 'framegen_all' create the source '.miff' files
# the rest fill out the 'frames_scale..' directories
# it's just a concatenation of 'preprocess_srcimg' and all the 'framegen_cmds' files

# create matching 'frames_scale00_png' directories and commands to convert the MIFF frames-directories
function GEN_PNG_CONVERSIONS()
{
    local RESCALE_PERCENTS=(10 20 25 30 50 75 100)
    local PNG_CONVERT_CMDS="framegen_convert_pngs.txt"
    local DIRECTORY_LIST="directory_list.txt"
    local DIRECTORY_LIST_PNG="directory_list_png.txt"
    
    for SS in ${RESCALE_PERCENTS[@]}; do
        FRAMES_DIR="frames_scale${SS}"
        PNG_DIR="png_${FRAMES_DIR}"
        
        if [[ -d "${PNG_DIR}" ]] then echo "exists: ${PNG_DIR}"; continue;
        else mkdir --verbose "${PNG_DIR}"; fi;
        
        echo convert-im6.q16 "'MIFF:${FRAMES_DIR}/frame*.miff'" +adjoin "'PNG:${PNG_DIR}/frame%03d.png'" >> ${PNG_CONVERT_CMDS}
    done; echo "";
    
    echo "" >> "${PNG_CONVERT_CMDS}"
    cat "${PNG_CONVERT_CMDS}"
}

# creates the 'png_frames_scale...' dirs and writes the commands
GEN_PNG_CONVERSIONS

# you'll have to execute the commands printed by 'GEN_PNG_CONVERSIONS' manually;
convert-im6.q16 'MIFF:frames_scale10/frame*.miff' +adjoin 'PNG:png_frames_scale10/frame%03d.png'
convert-im6.q16 'MIFF:frames_scale20/frame*.miff' +adjoin 'PNG:png_frames_scale20/frame%03d.png'
convert-im6.q16 'MIFF:frames_scale25/frame*.miff' +adjoin 'PNG:png_frames_scale25/frame%03d.png'
convert-im6.q16 'MIFF:frames_scale30/frame*.miff' +adjoin 'PNG:png_frames_scale30/frame%03d.png'
#convert-im6.q16 'MIFF:frames_scale50/frame*.miff' +adjoin 'PNG:png_frames_scale50/frame%03d.png'
convert-im6.q16 'MIFF:frames_scale75/frame*.miff' +adjoin 'PNG:png_frames_scale75/frame%03d.png'
#convert-im6.q16 'MIFF:frames_scale100/frame*.miff' +adjoin 'PNG:png_frames_scale100/frame%03d.png'

# for some reason 50% and 100% scaling causes fatal errors in ffmpeg / APNG encoder - something about multiple palettes
# an additional rescale of 99% or 101% seems to be a consistent workaround. '+map' doesn't help
convert-im6.q16 'MIFF:frames_scale50/frame*.miff' -scale 99% +adjoin 'PNG:png_frames_scale50/frame%03d.png'
convert-im6.q16 'MIFF:frames_scale100/frame*.miff' -scale 99% +adjoin 'PNG:png_frames_scale100/frame%03d.png'


function FINALCOMMANDS()
{
    local OUTPUT_DIR="webp_output"
    if [[ -d "${OUTPUT_DIR}" ]] then echo "# output dir: ${OUTPUT_DIR}";
    else mkdir --verbose "${OUTPUT_DIR}"; fi; echo "";
    
    local FRAMEDIRS=(frames_scale*)
    local PNG_FRAMEDIRS=(png_frames_scale*)
    local WEBP_DEFS="-quality 100 -define webp:thread-level=1 -define webp:use-sharp-yuv=true -define webp:lossless=true -define webp:method=6"
    #SUBDIRS=(${FRAMEDIRS[@]} ${PNG_FRAMEDIRS[@]})
    
    echo ""; echo "# WEBP"
    for SUBDIR in ${FRAMEDIRS[@]}; do
        local SCALENUM="${SUBDIR#frames_scale}"
        echo "convert-im6.q16 'MIFF:${SUBDIR}/frame*.miff' ${WEBP_DEFS} -adjoin 'WEBP:${OUTPUT_DIR}/rgb_scale${SCALENUM}.webp'"
    done; echo "";
    
    OUTPUT_DIR="ffmpeg_output"
    if [[ -d "${OUTPUT_DIR}" ]] then echo "# output dir: ${OUTPUT_DIR}";
    else mkdir --verbose "${OUTPUT_DIR}"; fi;
    
    echo "# ffmpeg MP4/APNG output"
    for SUBDIR in ${PNG_FRAMEDIRS[@]}; do
        local SCALENUM="${SUBDIR#png_frames_scale}"
        echo "ffmpeg -y -f image2 -framerate 60 -pattern_type sequence -i '${SUBDIR}/frame%03d.png' '${OUTPUT_DIR}/rgb_scale${SCALENUM}.mp4'"
        echo "ffmpeg -y -f image2 -framerate 60 -pattern_type sequence -i '${SUBDIR}/frame%03d.png' '${OUTPUT_DIR}/rgb_scale${SCALENUM}.apng'"
    done; echo "";
}

FINALCOMMANDS

# again, manually execute the final commands

# WEBP
convert-im6.q16 -verbose 'MIFF:frames_scale10/frame*.miff' -define webp:thread-level=1 -define webp:use-sharp-yuv=true -define webp:lossless=true -define webp:method=6 -quality 100 -adjoin 'WEBP:webp_output/rgb_scale10.webp'
convert-im6.q16 -verbose 'MIFF:frames_scale20/frame*.miff' -define webp:thread-level=1 -define webp:use-sharp-yuv=true -define webp:lossless=true -define webp:method=6 -quality 100 -adjoin 'WEBP:webp_output/rgb_scale20.webp'
convert-im6.q16 -verbose 'MIFF:frames_scale25/frame*.miff' -define webp:thread-level=1 -define webp:use-sharp-yuv=true -define webp:lossless=true -define webp:method=6 -quality 100 -adjoin 'WEBP:webp_output/rgb_scale25.webp'
convert-im6.q16 -verbose 'MIFF:frames_scale30/frame*.miff' -define webp:thread-level=1 -define webp:use-sharp-yuv=true -define webp:lossless=true -define webp:method=6 -quality 100 -adjoin 'WEBP:webp_output/rgb_scale30.webp'
convert-im6.q16 -verbose 'MIFF:frames_scale50/frame*.miff' -define webp:thread-level=1 -define webp:use-sharp-yuv=true -define webp:lossless=true -define webp:method=6 -quality 100 -adjoin 'WEBP:webp_output/rgb_scale50.webp'
convert-im6.q16 -verbose 'MIFF:frames_scale75/frame*.miff' -define webp:thread-level=1 -define webp:use-sharp-yuv=true -define webp:lossless=true -define webp:method=6 -quality 100 -adjoin 'WEBP:webp_output/rgb_scale75.webp'
convert-im6.q16 -verbose 'MIFF:frames_scale100/frame*.miff' -define webp:thread-level=1 -define webp:use-sharp-yuv=true -define webp:lossless=true -define webp:method=6 -quality 100 -adjoin 'WEBP:webp_output/rgb_scale100.webp'

# ffmpeg MP4/APNG output
ffmpeg -f image2 -framerate 60 -pattern_type sequence -i 'png_frames_scale10/frame%03d.png' 'ffmpeg_output/rgb_scale10.mp4'
ffmpeg -f image2 -framerate 60 -pattern_type sequence -i 'png_frames_scale10/frame%03d.png' 'ffmpeg_output/rgb_scale10.apng'
ffmpeg -f image2 -framerate 60 -pattern_type sequence -i 'png_frames_scale20/frame%03d.png' 'ffmpeg_output/rgb_scale20.mp4'
ffmpeg -f image2 -framerate 60 -pattern_type sequence -i 'png_frames_scale20/frame%03d.png' 'ffmpeg_output/rgb_scale20.apng'
ffmpeg -f image2 -framerate 60 -pattern_type sequence -i 'png_frames_scale25/frame%03d.png' 'ffmpeg_output/rgb_scale25.mp4'
ffmpeg -f image2 -framerate 60 -pattern_type sequence -i 'png_frames_scale25/frame%03d.png' 'ffmpeg_output/rgb_scale25.apng'
ffmpeg -f image2 -framerate 60 -pattern_type sequence -i 'png_frames_scale30/frame%03d.png' 'ffmpeg_output/rgb_scale30.mp4'
ffmpeg -f image2 -framerate 60 -pattern_type sequence -i 'png_frames_scale30/frame%03d.png' 'ffmpeg_output/rgb_scale30.apng'
ffmpeg -f image2 -framerate 60 -pattern_type sequence -i 'png_frames_scale50/frame%03d.png' 'ffmpeg_output/rgb_scale50.mp4'
ffmpeg -f image2 -framerate 60 -pattern_type sequence -i 'png_frames_scale50/frame%03d.png' 'ffmpeg_output/rgb_scale50.apng'
ffmpeg -f image2 -framerate 60 -pattern_type sequence -i 'png_frames_scale75/frame%03d.png' 'ffmpeg_output/rgb_scale75.mp4'
ffmpeg -f image2 -framerate 60 -pattern_type sequence -i 'png_frames_scale75/frame%03d.png' 'ffmpeg_output/rgb_scale75.apng'
ffmpeg -f image2 -framerate 60 -pattern_type sequence -i 'png_frames_scale100/frame%03d.png' 'ffmpeg_output/rgb_scale100.mp4'
ffmpeg -f image2 -framerate 60 -pattern_type sequence -i 'png_frames_scale100/frame%03d.png' 'ffmpeg_output/rgb_scale100.apng'


# miff -> png conversion with mogrify
# mogrify-im6.q16 -format png -path 'png_frames_scale50' -scale 50% 'MIFF:frames_scale50/frame*.miff'


