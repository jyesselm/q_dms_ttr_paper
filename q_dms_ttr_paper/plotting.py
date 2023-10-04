import matplotlib.pyplot as plt

from rna_secstruct_design.selection import get_selection, SecStruct


def colors_for_sequence(seq: str):
    """
    get colors for a sequence for DMS reactivity
    :param seq: sequence
    :return: list of colors
    """
    colors = []
    for e in seq:
        if e == "A":
            colors.append("red")
        elif e == "C":
            colors.append("blue")
        elif e == "G":
            colors.append("orange")
        else:
            colors.append("green")
    return colors


def find_stretches(nums):
    """
    Identify stretches of consecutive numbers
    :param nums: list of numbers
    :return: list of stretches
    """
    nums.sort()
    stretches = []
    start = end = nums[0]

    for num in nums[1:]:
        if num == end + 1:
            end = num
        else:
            stretches.append([start, end])
            start = end = num

    stretches.append([start, end])
    return stretches


def fill_between(ax, color, x, y, alpha=0.15, **kwargs):
    ax.fill_between(x, y, color=color, alpha=0.15, zorder=-1)


def plot_pop_avg(seq, ss, reactivities, ax=None, axis="sequence_structure"):
    colors = colors_for_sequence(seq)
    x = list(range(len(seq)))
    if ax is None:
        fig, ax = plt.subplots(1, figsize=(20, 4))
    ax.bar(range(0, len(reactivities)), reactivities, color=colors)
    ax.set_xticks(x)
    if axis == "sequence_structure":
        ax.set_xticklabels([f"{s}\n{nt}" for s, nt in zip(seq, ss)])
    elif axis == "sequence":
        ax.set_xticklabels([f"{s}" for s in seq])
    elif axis == "structure":
        ax.set_xticklabels([f"{s}" for s in ss])
    else:
        pass
    return ax


def plot_pop_avg_from_row(row, data_col="data", ax=None):
    return plot_pop_avg(row["sequence"], row["structure"], row[data_col], ax)


def plot_pop_avg_all(df, data_col="data", axis="sequence_structure", **kwargs):
    fig, axes = plt.subplots(len(df), 1, **kwargs)
    j = 0
    for i, row in df.iterrows():
        colors = colors_for_sequence(row["sequence"])
        axes[j].bar(range(0, len(row[data_col])), row[data_col], color=colors)
        axes[j].set_title(row["rna_name"])
        j += 1
    plot_pop_avg_from_row(df.iloc[-1], ax=axes[-1], axis=axis)
    return fig


def plot_pop_avg_titration(df, titration_col, highlights=None, **kwargs):
    fig, axes = plt.subplots(len(df), 1, **kwargs)
    j = 0
    secstruct = SecStruct(df.iloc[0]["sequence"], df.iloc[0]["structure"])
    highlight_bounds = []
    if highlights is None:
        highlights = []
    else:
        for h in highlights:
            selection = get_selection(secstruct, h)
            for bounds in find_stretches(selection):
                highlight_bounds.append(bounds)
    for i, row in df.iterrows():
        colors = colors_for_sequence(row["sequence"])
        axes[j].bar(range(0, len(row["data"])), row["data"], color=colors)
        axes[j].set_title(str(row[titration_col]) + " mM")
        axes[j].set_ylim([0, 0.1])
        axes[j].set_xlim([-0.1, len(row["data"]) + 0.1])
        axes[j].set_xticks([])
        for bounds in highlight_bounds:
            fill_between(axes[j], "gray", bounds, [0, 10])
        j += 1
    plot_pop_avg_from_row(df.iloc[-1], ax=axes[-1])
    return fig


# style functions #############################################################


def publication_style_ax(ax):
    for spine in ax.spines.values():
        spine.set_linewidth(2)
    ax.tick_params(width=2)
    fsize = 24
    ax.xaxis.label.set_fontsize(fsize)
    ax.yaxis.label.set_fontsize(fsize)
    ax.tick_params(axis="both", which="major", labelsize=fsize - 2)