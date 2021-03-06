
import pandas as pd
import re


class PhonemeToGrapheme:
    """
    A (very) simple rules based aproach to convert a string sequence of Portuguese SAMPA symbols into
    a written form of that sequence
    """
    def __init__(self, sampa_tsv_filename):
        self.sampa_df = pd.read_csv(sampa_tsv_filename, sep='\t', encoding="utf-8")

        self._sorted_phoneme_list = sorted(self.sampa_df["Symbol"], key=len, reverse=True)
        self._phoneme2grapheme = dict(zip(self.sampa_df["Symbol"], self.sampa_df["grapheme"]))

    def split_phonemes(self, string_of_phonemes):
        """
        since the SAMPA phonemes can be multi-character, this loops over the string and looks for the longest
        phoneme first at the start of the string
        :param string_of_phonemes:
        :return:
        """
        # very basic, assumes no ambiguity, inefficient
        position = 0
        phonemes = []
        while position < len(string_of_phonemes):
            orig_position = position
            string_to_check = string_of_phonemes[position:]
            # could use a regex, but what if we want special handling of '...'
            for phoneme in self._sorted_phoneme_list + ["..."]:
                if string_to_check.startswith(phoneme):
                    if phoneme not in ("...", "\"", "\\\"", ":"):
                        phonemes.append(phoneme)
                    position += len(phoneme)
                    break
            if orig_position == position:
                print(f"Cannot parse {string_of_phonemes} at {string_to_check}")
                phonemes = []
                position = len(string_of_phonemes)
        return phonemes

    def baseline_p2g(self, custom_pronunciation: str):
        """

        :param custom_pronunciation: e.g. [\"Ont6~j~]
            should be surrounded in square brackets
            can include ", :, ... and \ which will be stripped out
        :return: a 'word-like-string' which corresponds to the pronunciation
                e.g. ontêm
        """
        # some known problems:
        # S -> ch or s
        # accented e
        # z > s mid word ambiguous
        # 6~ w~ at end of word can be 'ão' or 'am' - might be some rule to this (?)
        custom_pronunciation = custom_pronunciation.strip("[]")
        # " = stress, : = lengthened vowel maybe, '...' = intraword pause probably
        custom_pronunciation = re.sub(r"[\"\\\:]", "", custom_pronunciation)
        
        phonemes = self.split_phonemes(custom_pronunciation)

        written_form = ""
        for i, phoneme in enumerate(phonemes):
            if phoneme in self._phoneme2grapheme:
                # exception for 'u' at end of word:
                if phoneme == "u" and i == len(phonemes)-1:
                    written_form += "o"
                else:
                    written_form += self._phoneme2grapheme[phoneme]
            else:
                raise Exception(f"Unknonwn phoneme: {phoneme}")
        return written_form


def main():

    p2g = PhonemeToGrapheme("sampa.tsv")

    print(p2g._sorted_phoneme_list)

    print(p2g._phoneme2grapheme)

    phoneme_string = "[\"viJu]"  # ['v', 'i', 'J', 'u']
    written_form = p2g.baseline_p2g(phoneme_string)
    print(written_form)

    phoneme_string = "[\"Ont6~j~]"  # ['O', 'n', 't', '6~j~']
    written_form = p2g.baseline_p2g(phoneme_string)
    print(written_form)

    p2g.sampa_df["p2g"] = p2g.sampa_df["Transcription"].apply(lambda x: p2g.baseline_p2g(x) if isinstance(x, str) else "")

    print(p2g.sampa_df)


if __name__ == '__main__':
    main()

    # for testing:
    # [6n"ojt@s:"er]  ( colon )
    # [iSpr6jt"a]  at 'j'
    # [n"6~w~:]  at w
    # t"6j~:  at ~

    """
    Cannot parse t"6j~: at ~:
    Cannot parse g6r@p"up@lu6:jS at jS
    Cannot parse d@Skubr"i:ws@ at ws@
    Cannot parse l"un6w at w
    Cannot parse fi...k"a...@j"u at j"u
    Cannot parse kumunic"a at c"a
    Cannot parse g"Oc6~w~ at c6~w~
    Cannot parse tevu:lz"6w~ at w~
    Cannot parse sÂ:j~ at Â:j~
    Cannot parse k6"ir6w~ at w~
    Cannot parse n6~:j~ at j~
    Cannot parse m"ej at j
    """


