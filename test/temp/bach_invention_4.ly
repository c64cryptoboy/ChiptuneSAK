\version "2.18.2"
\header {
composer = ""
}
\new StaffGroup <<
\new Staff \with { instrumentName = #"I" } {
\clef treble
% measure 1
| \time 3/8 \key d \minor d'16 e'16 f'16 g'16 a'16 bes'16
% measure 2
| des'16 bes'16 a'16 g'16 f'16 e'16
% measure 3
| f'8 a'8 d''8
% measure 4
| g'8 des''8 e''8
% measure 5
| d''16 e''16 f''16 g''16 a''16 bes''16
% measure 6
| des''16 bes''16 a''16 g''16 f''16 e''16
% measure 7
| f''16 d''16 e''16 f''16 g''16 a''16
% measure 8
| bes'16 a''16 g''16 f''16 e''16 d''16
% measure 9
| e''16 c''16 d''16 e''16 f''16 g''16
% measure 10
| a'16 g''16 f''16 e''16 d''16 c''16
% measure 11
| d''16 e''16 f''16 d''16 e''16 f''16
% measure 12
| g'8 r4
% measure 13
| c''16 d''16 e''16 c''16 d''16 e''16
% measure 14
| f'8 r8 bes'8~
% measure 15
| bes'8 a'8 g'8
% measure 16
| c''16 bes'16 a'16 g'16 f'16 e'16
% measure 17
| f'16 g'16 g'8. f'16
% measure 18
| f'8 c''8 c''8
% measure 19
| c''4.~
% measure 20
| c''4.~
% measure 21
| c''4.~
% measure 22
| c''16 bes'16 a'16 g'16 f'16 e'16
% measure 23
| c''16 d'16 e'16 ges'16 g'16 a'16
% measure 24
| bes'16 a'16 g'16 f'16 e'16 d'16
% measure 25
| bes'16 c'16 d'16 e'16 f'16 g'16
% measure 26
| a'16 b'16 c''16 d''16 e''16 f''16
% measure 27
| aes'16 f''16 e''16 d''16 c''16 b'16
% measure 28
| c''16 b'16 d''16 c''16 b'16 a'16
% measure 29
| aes'16 a'16 aes'16 ges'16 e'16 d'16
% measure 30
| c'16 d'16 e'16 ges'16 aes'16 a'16
% measure 31
| d'16 c''16 b'16 a'16 aes'16 ges'16
% measure 32
| e'16 ges'16 aes'16 a'16 b'16 c''16
% measure 33
| ges'16 e''16 d''16 c''16 b'16 a'16
% measure 34
| aes'16 a'16 b'16 c''16 d''16 e''16
% measure 35
| a'16 f''16 e''16 d''16 c''16 b'16
% measure 36
| a''16 aes''16 ges''16 e''16 a''8~
% measure 37
| a''16 d''16 b'8. a'16
% measure 38
| a'8. a'16 bes'16 c''16
% measure 39
| d'8 ges'8 a'8
% measure 40
| bes'16 g'16 a'16 bes'16 c''16 d''16
% measure 41
| e'16 d''16 c''16 bes'16 a'16 g'16
% measure 42
| a'8 f''16 e''16 f''8
% measure 43
| g'8 e''8 r8
% measure 44
| d''16 e''16 f''16 g''16 a''16 bes''16
% measure 45
| des''16 bes''16 a''16 g''16 f''16 e''16
% measure 46
| f''8 d''8 g'8~
% measure 47
| g'16 d''16 des''16 e''16 a'16 des''16
% measure 48
| d''16 b'16 des''8. d''16
% measure 49
| d''16 c''16 bes'16 a'16 g'16 f'16
% measure 50
| bes'16 des'16 d'16 e'16 f'16 g'16
% measure 51
| a'16 d''16 f'8 e'16 d'16
% measure 52
| d'4~ d'16 r16
\bar "||"
}
\new Staff \with { instrumentName = #"II" } {
\clef bass
% measure 1
| \time 3/8 \key d \minor r4.
% measure 2
| r4.
% measure 3
| d16 e16 f16 g16 a16 bes16
% measure 4
| des16 bes16 a16 g16 f16 e16
% measure 5
| f8 a8 d'8
% measure 6
| e8 g8 des'8
% measure 7
| d8 d'8 f8
% measure 8
| g8 a8 bes8
% measure 9
| c8 c'8 e8
% measure 10
| f8 g8 a8
% measure 11
| bes16 g16 a16 bes16 c'16 d'16
% measure 12
| e16 d'16 c'16 bes16 a16 g16
% measure 13
| a16 f16 g16 a16 bes16 c'16
% measure 14
| d16 c'16 bes16 a16 g16 f16
% measure 15
| e16 c16 d16 e16 f16 g16
% measure 16
| a,16 g16 f16 e16 d16 c16
% measure 17
| d16 bes,16 c8 \ottava #-1 c,8
% measure 18
| f,16 g,16 \ottava #0 a,16 bes,16 c16 d16
% measure 19
| \ottava #-1 e,16 \ottava #0 d16 c16 bes,16 a,16 g,16
% measure 20
| a,16 bes,16 c16 d16 e16 f16
% measure 21
| g,16 f16 e16 d16 c16 bes,16
% measure 22
| a,16 bes,16 c16 a,16 bes,16 c16
% measure 23
| ges,8 r4
% measure 24
| g,16 a,16 bes,16 g,16 a,16 bes,16
% measure 25
| \ottava #-1 e,8 r4
% measure 26
| f,8 \ottava #0 f8 d8
% measure 27
| b,8 aes,8 \ottava #-1 e,8
% measure 28
| \ottava #0 a,16 aes,16 a,16 b,16 c16 d16
% measure 29
| e4.~
% measure 30
| e4.~
% measure 31
| e4.~
% measure 32
| e4.~
% measure 33
| e4.~
% measure 34
| e8 e'8 d'8
% measure 35
| c'8 b8 a8
% measure 36
\clef treble | d'8 e'8 f'8
% measure 37
\clef bass | d'8 e'8 e8
% measure 38
| a16 a,16 bes,16 c16 d16 ees16
% measure 39
| ges,16 ees16 d16 c16 bes,16 a,16
% measure 40
| g,8. g,16 a,16 bes,16
% measure 41
| \ottava #-1 c,8 g,8 \ottava #0 c8
% measure 42
| f16 g16 a16 b16 des'16 d'16
% measure 43
| e16 d'16 des'16 b16 a16 g16
% measure 44
| f8 a8 d'8
% measure 45
| e8 g8 des'8
% measure 46
| d16 e16 f16 g16 a16 bes16
% measure 47
| des16 bes16 a16 g16 f16 e16
% measure 48
| f16 g16 a8 a,8
% measure 49
| bes,8. c16 bes,16 a,16
% measure 50
| g,16 bes16 a16 g16 f16 e16
% measure 51
| f16 g16 a8 a,8
% measure 52
| \ottava #-1 d,4~ d,16 r16
\bar "||"
}
>>
