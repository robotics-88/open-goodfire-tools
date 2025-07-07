from pathlib import Path
import argparse

class StorePathAction(argparse.Action):
    def __call__(self, parser, args, values, option_string=None):
        setattr(args, self.dest, Path(values))