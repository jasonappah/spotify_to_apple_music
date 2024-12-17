# spotify_to_apple_music

inspired by https://github.com/simonschellaert/spotify2am/tree/master?tab=readme-ov-file

matches songs between spotify and apple by using a track's ISRC so almost always gets the exact same song on both platforms. was expecting to have to fall back to some other heuristics for matching songs but my entire spotify library had ISRCs which made things a lot easier. not sure if i j got lucky or if this is fairly common

for a single playlist of ~2.5k songs:
- ingest took 64 seconds
- apply took TBD seconds
- matching ISRCs between spotify and apple failed 0 times\*
  - \*...once I realized that spotify sometimes returns ISRCs with lower case characters :/ after uppercasing ISRCs on ingest we were good to go. ISRC is technically case insensitive but typically presented in uppercase. all the ISRCs i've looked at on apple's api are uppercased but spotify seems to be a bit more lax
