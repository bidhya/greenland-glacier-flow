
###################################################################################################
# Imports.
###################################################################################################

import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("agg") # Write to file rather than window.




###################################################################################################
# Functions.
###################################################################################################

def plot_velocity(vel_array, extent, vmax, out_fpath):
    """Plot velocity using matplotlib"""
    im = plt.imshow(vel_array, extent=extent, cmap="turbo", vmin=0, vmax=vmax)
    cbar = plt.colorbar(im)
    cbar.set_label("Velocity [m d$^{-1}$]")
    plt.gca().ticklabel_format(
        useOffset=False, style="plain"  # remove scientific notation
    )
    plt.xticks(fontsize=7)
    plt.yticks(fontsize=7, rotation=90, va="center")
    plt.tight_layout()
    plt.savefig(out_fpath, dpi=600)
    plt.close()


def plot_velocity_diff(vel_array, extent, vmax, out_fpath):
    """
    Plot velocity difference using matplotlib.
    """
    im = plt.imshow(vel_array, extent=extent,
                    cmap="viridis", vmin=0, vmax=vmax)
    cbar = plt.colorbar(im)
    cbar.set_label("Displacement from expected flow [m]")
    plt.gca().ticklabel_format(
        useOffset=False, style="plain"  # remove scientific notation
    )
    plt.xticks(fontsize=7)
    plt.yticks(fontsize=7, rotation=90, va="center")
    plt.tight_layout()
    plt.savefig(out_fpath, dpi=600)
    plt.close()