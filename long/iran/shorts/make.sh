#!/bin/bash
# teaser Shorts cut from the long video: segments -> 1080x1920 (blurred bg, video centered, title on top)
set -e; cd "$(dirname "$0")"; SRC=../Chain_Secrets_Trump_Iran_34_Times.mp4; F=../../fonts/InterDisplay-Black.otf; M=../../fonts/Inter-SemiBold.otf
mk() { # name "t1 t2;t3 t4" line1 line2
  n=$1; i=0; : > l.txt
  for seg in $(echo "$2" | tr ';' ' ' | xargs -n2 | tr ' ' ','); do a=${seg%,*}; b=${seg#*,}
    ffmpeg -v error -y -ss $a -to $b -i $SRC -c:v libx264 -preset veryfast -crf 18 -c:a aac -b:a 192k seg$i.mp4; echo "file 'seg$i.mp4'" >> l.txt; i=$((i+1)); done
  ffmpeg -v error -y -f concat -safe 0 -i l.txt -c copy cat.mp4
  D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 cat.mp4)
  ffmpeg -v error -y -i cat.mp4 -filter_complex "[0:v]split[a][b];[a]scale=-2:1920,crop=1080:1920,boxblur=30:2,eq=brightness=-0.25[bg];[b]scale=1080:-2[fg];[bg][fg]overlay=0:(H-h)/2,\
drawtext=fontfile=$F:text='$3':fontsize=82:fontcolor=white:x=(w-tw)/2:y=330,\
drawtext=fontfile=$F:text='$4':fontsize=82:fontcolor=0xE84148:x=(w-tw)/2:y=430,\
drawtext=fontfile=$M:text='Full investigation on the channel':fontsize=44:fontcolor=0xC8CCD6:x=(w-tw)/2:y=1460[v]" \
   -map "[v]" -map 0:a -af "afade=t=in:d=0.25,afade=t=out:st=$(python3 -c "print($D-0.6)"):d=0.6" -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -c:a aac -b:a 192k -movflags +faststart $n.mp4
  rm -f seg*.mp4 cat.mp4 l.txt; echo "$n $D"
}
mk short1_34_times "0 7.75;34.55 80.3" "HE SAID IT" "34 TIMES"
mk short2_coin_flip "377.9 415.2" "34 PROMISES." "BITCOIN DID THIS"
