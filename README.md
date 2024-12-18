# spotify_to_apple_music

inspired by https://github.com/simonschellaert/spotify2am/tree/master?tab=readme-ov-file

matches songs between spotify and apple by using a track's [ISRC](https://isrc.ifpi.org/en/) so almost always gets the exact same song on both platforms. was expecting to have to fall back to some other heuristics for matching songs but my entire spotify library had ISRCs which made things a lot easier. not sure if i j got lucky or if this is fairly common

## results
for 8 playlists consisting of 2.3k unique songs and 2.6k playlist tracks:
- ingest took 61 seconds
- apply took 42 seconds
- 77 songs (~3%) didn't get matched between spotify and apple
  - i'm sure there are some errors, but the couple songs i looked at manually weren't even on apple's library
  
spotify sometimes returns ISRCs with lower case characters which wasted a lot of my time :/ once i figured this out, i just uppercase all ISRCs on ingest we were good to go. ISRC is technically case insensitive but typically presented in uppercase. all the ISRCs i've looked at on apple's api are uppercased but spotify seems to be a bit more lax
