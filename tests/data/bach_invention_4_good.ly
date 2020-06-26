\version "2.18.2"

        \paper { 
        indent=0\mm line-width=120\mm oddHeaderMarkup = ##f
        evenHeaderMarkup = ##f oddFooterMarkup = ##f evenFooterMarkup = ##f 
        page-breaking = #ly:one-line-breaking }
    
\new Staff  {
\time 3/8 \key f \major | g'8 cis''8 e''8
| d''16 e''16 f''16 g''16 a''16 ais''16
}