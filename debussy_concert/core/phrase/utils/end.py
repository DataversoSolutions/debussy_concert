from debussy_concert.core.phrase.phrase_base import PhraseBase
from debussy_concert.core.motif.end import EndMotif


class EndPhrase(PhraseBase):
    def __init__(self, end_motif=None, name=None) -> None:
        self.end_motif = end_motif or EndMotif()
        super().__init__(
            name=name,
            motifs=[self.end_motif]
        )
