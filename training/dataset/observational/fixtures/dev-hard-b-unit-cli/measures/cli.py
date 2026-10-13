from .units import convert


def cli_main(argv):
    meters = float(argv[0])
    return convert(meters, "m")
