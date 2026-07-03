from everest_models.jobs.fm_plume_static.parser import build_argument_parser
from everest_models.jobs.fm_plume_static.tasks import run_plume_static

FULL_JOB_NAME = "Plume static"


def main_entry_point(args=None):
    args_parser = build_argument_parser()
    options = args_parser.parse_args(args)

    if options.lint:
        args_parser.exit()

    return run_plume_static(
        options.config,
        case_name=options.case_name,
    )
