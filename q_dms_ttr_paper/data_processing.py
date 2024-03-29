import pandas as pd
import numpy as np
from pathlib import Path
from typing import List

from seq_tools import has_5p_sequence, to_rna
from seq_tools import trim as seq_ss_trim
from seq_tools import SequenceStructure
from seq_tools.structure import find as seq_ss_find
from rna_secstruct import SecStruct, MotifSearchParams


from q_dms_ttr_paper.logger import get_logger
from q_dms_ttr_paper.titration import compute_mg_1_2


log = get_logger("DATA-PROCESSING")
DATA_PATH = "data"
RESOURCES_PATH = "q_dms_ttr_paper/resources"


def get_data(path, sets) -> pd.DataFrame:
    dfs = []
    for run_name in sets:
        full_path = Path(path) / f"{run_name}.json"
        if not full_path.exists():
            raise FileNotFoundError(f"File {full_path} does not exist")
        df = pd.read_json(full_path)
        dfs.append(df)
    return pd.concat(dfs)


def trim(df: pd.DataFrame, start: int, end: int) -> pd.DataFrame:
    """
    trims the dataframe to the given start and end
    :param df: a dataframe with data
    :param start: the start index
    :param end: the end index
    :return: a trimmed dataframe
    """
    df = seq_ss_trim(df, start, end)
    if start == 0:
        df["data"] = df["data"].apply(lambda x: x[:-end])
    elif end == 0:
        df["data"] = df["data"].apply(lambda x: x[start:])
    elif start == 0 and end == 0:
        df["data"] = df["data"].apply(lambda x: x)
    else:
        df["data"] = df["data"].apply(lambda x: x[start:-end])
    return df


def trim_p5_and_p3(df):
    """
    trims the 5' and 3' ends of the data
    :param df: a dataframe with data
    :return: a trimmed dataframe
    """
    df_p5 = pd.read_csv(f"{RESOURCES_PATH}/csvs/p5_sequences.csv")
    df_p5 = to_rna(df_p5)
    common_p5_seq = ""
    for p5_seq in df_p5["sequence"]:
        if has_5p_sequence(df, p5_seq):
            common_p5_seq = p5_seq
    if len(common_p5_seq) == 0:
        raise ValueError("No common p5 sequence found")
    log.info(f"common p5 sequence: {common_p5_seq}")
    return trim(df, len(common_p5_seq), 20)


def get_dms_reactivity_for_motif(df, params, error=True):
    """
    finds a specific sequence and structure in each construct and returns them
    """
    params = MotifSearchParams(**params)
    data_len = len(params.sequence) - params.sequence.count("&")
    all_data = []
    for _, row in df.iterrows():
        ss = SecStruct(row["sequence"], row["structure"])
        motifs = ss.get_motifs(params)
        if len(motifs) != 1 and error:
            raise ValueError("More than one motif found")
        elif len(motifs) == 0:
            all_data.append([-1] * data_len)
            continue
        data = []
        for s in motifs[0].strands:
            for e in s:
                data.append(row["data"][e])
        all_data.append(data)
    return all_data


def get_dms_reactivity_for_sub_structure(
    df: pd.DataFrame,
    sub_seq_struct: SequenceStructure,
    start=None,
    end=None,
    error=True,
) -> List[List[float]]:
    all_data = []
    data_len = len(sub_seq_struct.sequence) - sub_seq_struct.sequence.count("&")
    for i, row in df.iterrows():
        ss = SequenceStructure(row["sequence"], row["structure"])
        r = seq_ss_find(ss, sub_seq_struct, start, end)
        if len(r) == 0 and error:
            msg = (
                f"Could not find seq:{sub_seq_struct.sequence} "
                f"ss:{sub_seq_struct.structure} in {row['name']} with seq "
                f"{row['sequence']} and ss {row['structure']}"
            )
            raise ValueError(msg)
        elif len(r) == 0:
            all_data.append([-1] * data_len)
            continue
        elif len(r) > 1:
            msg = (
                f"multiple copies of seq:{sub_seq_struct.sequence} "
                f"ss:{sub_seq_struct.structure} in {row['name']} with seq "
                f"{row['sequence']} and ss {row['structure']}"
            )
            raise ValueError(msg)
        pos = []
        bounds = r[0]
        for r in bounds:
            pos.extend(list(range(r[0], r[1])))
        all_data.append([row["data"][p] for p in pos])
    return all_data


def get_dms_reactivity_for_wt_tlr(df, start=None, end=None, error=True):
    # TODO okay this is a problem have to search in a specfic direction.
    # m_ss = structure.SequenceStructure("CCUAAG&UAUGG", "((...(&)..))")
    m_ss = SequenceStructure("UAUGG&CCUAAG", "(..((&))...)")
    data_len = len(m_ss.sequence) - m_ss.sequence.count("&")
    all_data = []
    for i, row in df.iterrows():
        ss = SequenceStructure(row["sequence"], row["structure"])
        r = seq_ss_find(ss, m_ss, start, end)
        if len(r) == 0 and error:
            msg = (
                f"Could not find the tetraloop receptor "
                f"in {row['name']} with seq "
                f"{row['sequence']} and ss {row['structure']}"
            )
            raise ValueError(msg)
        elif len(r) == 0:
            all_data.append([-1] * data_len)
            continue
        elif len(r) > 1:
            msg = (
                f"multiple copies of the tetraloop receptor where found  "
                f"in {row['name']} with seq "
                f"{row['sequence']} and ss {row['structure']}"
            )
            raise ValueError(msg)
        bounds = r[0]
        data = (
            row["data"][bounds[1][0] : bounds[1][1]]
            + row["data"][bounds[0][0] : bounds[0][1]]
        )
        all_data.append(data)
    return all_data


# reused processing functions #########################################################


def get_gaaa_data(df, error=True):
    """
    generates two new columns in the dataframe one with the gaaa reactivity data
    and one with the average gaaa reactivity data
    :params df: a dataframe with data
    """
    df["gaaa"] = get_dms_reactivity_for_sub_structure(
        df, SequenceStructure("GGAAAC", "(....)"), error=error
    )
    df["gaaa_avg"] = df["gaaa"].apply(lambda x: np.mean(x[2:-1]))


# specific library processing #########################################################
# for chemical mapping sequencing runs ################################################


class DataProcessor:
    def load_data(self):
        """
        get data from the raw folder and load it into a dataframe
        """
        pass

    def clean_data(self):
        """
        makes sure we have the correct data removes any duplicates and data that
        is not related to the project
        """
        pass

    def process_data(self):
        """
        performs any processing for the data to be useful after. This includes
        getting data on motifs, mutational analysis, titraiton analysis, etc
        """
        pass


"""
MTTR6BufferTitrationDataProcessor - covers wild-type sequence with different buffer 
conditions

MTTR6MgTitrationDataProcessor - covers wild-type sequence with different mg conditions

MTTR6MutsDataProcessor - covers point mutants of the wild-type sequence such as uucg / 
no-tlr and their mg titrations

TTRMutsDataProcessor - covers the library of mutations from steves paper
"""


class MTTR6BufferTitrationDataProcessor(DataProcessor):
    """
    This covers the original data tests to find the idea buffer conditions
    """

    def __init__(self):
        self.name = "MTTR6BufferTitrationDataProcessor"
        self.df: pd.DataFrame = None

    def load_data(self):
        runs = [
            "2022_07_26_minittr-6-2HP-ref_buffer_seq",
            "2022_07_20_minittr_Hepes-titra_seq",
        ]
        self.df = get_data(DATA_PATH + "/sequencing_runs/raw", runs)

    def clean_data(self):
        # ensure data is rna
        self.df = to_rna(self.df)
        # remove p5 and p3 sequence
        # remove constructs not related to this analysis
        include = ["minittr-6-2HP-ref"]
        self.df = self.df[self.df["name"].isin(include)]
        # these experiments dont seem to be related to this analysis
        exclude_exps = [
            "2022_07_18_C0117_100mM_buffer_Mg2+_titra_CM_BL"
            "2022_07_18_minittr-6-2HP-ref_NaC_titra_No_MgCl2_CM_RG",
            "2022_07_19_C0117_Hepes_titra_CM_BL",
        ]
        self.df = self.df[~self.df["exp_name"].isin(exclude_exps)]
        # why do I need this extra line??
        self.df = self.df[
            ~(
                self.df["exp_name"]
                == "2022_07_18_minittr-6-2HP-ref_NaC_titra_No_MgCl2_CM_RG"
            )
        ]

    def process_data(self):
        # remove common p5 and p3 sequences
        self.df = trim_p5_and_p3(self.df)
        # get GAAA tetraloop reactivity data
        get_gaaa_data(self.df)
        self.df["tlr"] = get_dms_reactivity_for_wt_tlr(self.df)
        # get the first reference hairpin at the 5' end
        self.df["ref_hp_1"] = get_dms_reactivity_for_sub_structure(
            self.df, SequenceStructure("CGAGUAG", "(.....)"), end=50
        )
        self.df["ref_hp_1_as"] = self.df["ref_hp_1"].apply(
            lambda x: np.mean([x[2], x[5]])
        )
        # get the second reference hairpin at the 3' end
        self.df["ref_hp_2"] = get_dms_reactivity_for_sub_structure(
            self.df, SequenceStructure("CGAGUAG", "(.....)"), start=50
        )
        self.df["ref_hp_2_as"] = self.df["ref_hp_2"].apply(
            lambda x: np.mean([x[2], x[5]])
        )
        # get the ires motif
        self.df["ires"] = get_dms_reactivity_for_motif(
            self.df, {"sequence": "GAACUAC&GC", "structure": "(.....(&))"}
        )
        # get kinke turn motif
        self.df["kink_turn"] = get_dms_reactivity_for_sub_structure(
            self.df, SequenceStructure("CCGAG&CGUUUGACG", "(((((&)..)))..)")
        )
        # get the 3x3 motif
        self.df["3x3_motif"] = get_dms_reactivity_for_sub_structure(
            self.df, SequenceStructure("GAACA&UACCC", "(...(&)...)")
        )

        self.df.to_json(
            "data/sequencing_runs/processed/wt_buffer_titra.json", orient="records"
        )


class MTTR6MgTitrationDataProcessor(DataProcessor):
    """ """

    def __init__(self):
        self.name = "MTTR6MgTitrationDataProcessor"
        self.df: pd.DataFrame = None

    def load_data(self):
        runs = [
            "2022_07_27_minittr_50mM_NaC_Mg_titra_seq",
            "2022_07_28_minittr_0.1M_NaC_Mg_titra_seq",
            "2022_07_29_minittr_0.15M_NaC_Mg_titr_seq",
            "2022_08_09_minittr_0.2M_NaC_Mg_titra_seq",
            "2022_08_10_minittr_0.25M_Mg_titr_seq",
            "2022_08_11_minittr_0.3M_NaC_Mg_titra_seq",
        ]
        self.df = get_data(DATA_PATH + "/sequencing_runs/raw/", runs)

    def clean_data(self):
        # ensure data is rna
        self.df = to_rna(self.df)
        # remove p5 and p3 sequence
        # remove constructs not related to this analysis
        include = ["minittr-6-2HP-ref"]
        self.df = self.df[self.df["name"].isin(include)]

    def process_data(self):
        self.df = trim_p5_and_p3(self.df)
        # get motif data
        # get GAAA tetraloop reactivity data
        get_gaaa_data(self.df)
        self.df["tlr"] = get_dms_reactivity_for_wt_tlr(self.df)
        # get the first reference hairpin at the 5' end
        self.df["ref_hp_1"] = get_dms_reactivity_for_sub_structure(
            self.df, SequenceStructure("CGAGUAG", "(.....)"), end=50
        )
        self.df["ref_hp_1_as"] = self.df["ref_hp_1"].apply(
            lambda x: np.mean([x[2], x[5]])
        )
        # get the second reference hairpin at the 3' end
        self.df["ref_hp_2"] = get_dms_reactivity_for_sub_structure(
            self.df, SequenceStructure("CGAGUAG", "(.....)"), start=50
        )
        self.df["ref_hp_2_as"] = self.df["ref_hp_2"].apply(
            lambda x: np.mean([x[2], x[5]])
        )
        # get the ires motif
        self.df["ires"] = get_dms_reactivity_for_motif(
            self.df, {"sequence": "GAACUAC&GC", "structure": "(.....(&))"}
        )
        # get kinke turn motif
        self.df["kink_turn"] = get_dms_reactivity_for_sub_structure(
            self.df, SequenceStructure("CCGAG&CGUUUGACG", "(((((&)..)))..)")
        )
        # get the 3x3 motif
        self.df["3x3_motif"] = get_dms_reactivity_for_sub_structure(
            self.df, SequenceStructure("GAACA&UACCC", "(...(&)...)")
        )
        self.df.to_json(
            "data/sequencing_runs/processed/wt_mg_titra.json", orient="records"
        )


class MTTR6MutsDataProcessor(DataProcessor):
    """
    This covers the point mutants for the wild-type
    """

    def __init__(self):
        self.name = "MTTR6MutsDataProcessor"
        self.df: pd.DataFrame = None

    def load_data(self):
        runs = [
            "2023_03_13_no_tlr_Mg_titra_redo_seq",
            "2023_02_02_minittr_6_uucg_Mg_titra_seq",
            "2023_02_17_no_3_3_junc_Mg_titr_seq",
            "2023_03_10_h1_3bp_longer_seq",
            "2023_03_14_no_ires_Mg_titr_redo_seq",
            "2023_03_15_h2_3bp_longer_Mg_titra_seq",
            "2023_03_22_h3_3bp_longer_Mg_titra_seq",
        ]
        self.df = get_data(DATA_PATH + "/sequencing_runs/raw", runs)
        # remove anything that does not have minittr in the name
        self.df = self.df[self.df["name"].str.contains("minittr")]

    def clean_data(self):
        pass

    def process_data(self):
        # remove common p5 and p3 sequences
        self.df = trim_p5_and_p3(self.df)
        # get GAAA tetraloop reactivity data
        get_gaaa_data(self.df, error=False)
        self.df["tlr"] = get_dms_reactivity_for_wt_tlr(self.df, error=False)
        self.df["ref_hp_1"] = get_dms_reactivity_for_sub_structure(
            self.df, SequenceStructure("CGAGUAG", "(.....)"), end=50
        )
        self.df["ref_hp_1_as"] = self.df["ref_hp_1"].apply(
            lambda x: np.mean([x[2], x[5]])
        )
        self.df["ires"] = get_dms_reactivity_for_motif(
            self.df, {"sequence": "GAACUAC&GC", "structure": "(.....(&))"}, error=False
        )
        self.df["3x3_motif"] = get_dms_reactivity_for_sub_structure(
            self.df, SequenceStructure("GAACA&UACCC", "(...(&)...)"), error=False
        )
        self.df["kink_turn"] = get_dms_reactivity_for_sub_structure(
            self.df, SequenceStructure("CCGAG&CGUUUGACG", "(((((&)..)))..)")
        )
        self.df.to_json(
            "data/sequencing_runs/processed/mttr6_muts_titra.json", orient="records"
        )


class TTRMutsDataProcessor:
    """
    This is the library of approximately 100 mutations that we have for TTR from
    steves bonilla's paper.
    """

    def __init__(self):
        self.name = "TTRMutsDataProcessor"
        self.df: pd.DataFrame = None

    def load_data(self):
        runs = [
            "2022_08_25_mtt6_set4_1st3_seq",
            "2022_08_26_mtt6_set4_2nd3_seq",
            "2022_08_26_mtt6_set1-3_MgTitra_KU_seq",
            "2022_08_29_mtt6_seq",
            "2022_08_30_mtt6_set4_seq",
            "2022_08_31_mtt6_set4_seq",
            "2022_09_01_mtt6_set4_seq",
        ]
        self.df = get_data(DATA_PATH + "/sequencing_runs/raw", runs)

    def clean_data(self):
        # ensure data is rna
        self.df = to_rna(self.df)
        # fix some errors in the data
        # 0.20 was set instead of 0.25 for some constructs
        self.df.loc[self.df["mg_conc"] == 0.20, "mg_conc"] = 0.25
        # remove constructs not related to this analysis
        exclude = ["PurRe4L5", "PtrRe2L5", "PurRe2L4"]
        self.df = self.df.query("name not in @exclude")
        # duplicate data not sure right now which is better
        q1 = self.df["run_name"] == "2022_08_29_mtt6_seq"
        q2 = self.df["rna_name"] == "mtt6_mutations_set_2_50mM-NaC_0.1-mM-Mg2+"
        self.df = self.df[~(q1 & q2)]
        q1 = self.df["run_name"] == "2022_08_29_mtt6_seq"
        q3 = self.df["rna_name"] == "mtt6_mutations_set_1_50mM-NaC_5-mM-Mg2+"
        self.df = self.df[~(q1 & q3)]
        # check there are no duplicates
        duplicates = self.__get_duplicates(self.df)
        if len(duplicates) > 0:
            log.error("There are duplicates in the data")
            for d in duplicates:
                log.error(d)
            exit()
        # round data
        # for the data column round each value to 5 decimal places
        self.df["data"] = self.df["data"].apply(lambda x: [round(y, 5) for y in x])

    def process_data(self):
        # remove common p5 and p3 sequences
        self.df = trim_p5_and_p3(self.df)
        # grab original rna_map experimental data from steves paper
        df_ref = pd.read_csv(f"data/construct_design/sets/all_sets.csv")
        df_ref = df_ref[["name", "dg", "dg_err", "act_seq", "act_ss"]]
        self.df = self.df.merge(df_ref, on="name")
        # get GAAA tetraloop reactivity data
        self.df["gaaa"] = get_dms_reactivity_for_sub_structure(
            self.df, SequenceStructure("GGAAAC", "(....)")
        )
        # get averaged value over the 3As in the tetraloop
        self.df["gaaa_avg"] = self.df["gaaa"].apply(lambda x: np.mean(x[2:-1]))
        # get reference hairpin at the 5' end of each construct
        self.df["ref_hp"] = get_dms_reactivity_for_sub_structure(
            self.df, SequenceStructure("CGAGUAG", "(.....)"), end=50
        )
        # get averaged value of the 2 As in the hairpin
        self.df["ref_hp_as"] = self.df["ref_hp"].apply(lambda x: np.mean([x[2], x[5]]))
        self.df = self.__get_tlr_reactivities(self.df)
        # make sure I save locally
        self.df.to_json(
            "data/sequencing_runs/processed/mttr6_data_full.json", orient="records"
        )

    def __get_duplicates(self, df):
        duplicates = []
        for i, g in df.groupby(["name", "mg_conc"]):
            unique_runs = g["run_name"].unique()
            unique_rna = g["rna_name"].unique()
            if len(unique_runs) == 1:
                continue
            duplicates.append((i, unique_runs, unique_rna))
        return duplicates

    def __get_tlr_reactivities(self, df) -> pd.DataFrame:
        all_data = []
        for i, row in df.iterrows():
            full_ss = SequenceStructure(row["sequence"], row["structure"])
            ss = SequenceStructure(row["act_seq"], row["act_ss"])
            bounds = seq_ss_find(full_ss, ss)[0]
            # trims off last basepair of 5' and first basepair of 3'
            # flips the orientation to match aligend sequence and structure
            data = (
                row["data"][bounds[1][0] : bounds[1][1] - 1]
                + row["data"][bounds[0][0] + 1 : bounds[0][1]]
            )
            all_data.append(data)
        df["tlr"] = all_data
        return df

    def __assign_tlr_reactivity(self, row, data):
        new_cols = {}
        insert_pos = []
        for insert in row["inserts"]:
            pos = int(insert[:-1])
            insert_pos.append(pos)
        mapped_pos = 1
        pos = 0
        new_cols["tlr"] = []
        new_cols["tlr_norm"] = []
        while pos < len(data):
            if mapped_pos in insert_pos:
                new_cols["tlr"].append(data[pos])
                new_cols["tlr_norm"].append(data[pos] / row["ref_hp_as"])
                new_cols[f"tlr_in_{mapped_pos}"] = data[pos + 1] / row["ref_hp_as"]
                pos += 1
            else:
                new_cols["tlr"].append(data[pos])
                new_cols["tlr_norm"].append(data[pos] / row["ref_hp_as"])
            mapped_pos += 1
            pos += 1
        return new_cols


# compute mg 1 / 2 ###################################################################


def compute_all_mg_1_2(df):
    """
    for each construct in mttr6 ttr mutant set compute the mg 1/2
    """
    data = []
    df = df[df["mg_conc"] != 5.0]
    for name, g in df.groupby(["name"]):
        r = compute_mg_1_2(g["mg_conc"], g["gaaa_avg"])
        data.append(
            {
                "name": name,
                "num_points": len(g),
                "mg_1_2": r[0][0],
                "mg_1_2_err": r[1][0],
                "n": r[0][1],
                "n_err": r[1][1],
                "a_0": r[0][2],
                "a_0_err": r[1][2],
            }
        )
    df_results = pd.DataFrame(data)
    return df_results
