from everest_models.jobs.fm_plume_dynamic.parser import build_argument_parser
from everest_models.jobs.fm_plume_dynamic.tasks import run_plume_dynamic

FULL_JOB_NAME = "Plume dynamic"


def main_entry_point(args=None):
    args_parser = build_argument_parser()
    options = args_parser.parse_args(args)

    if options.lint:
        args_parser.exit()

    return run_plume_dynamic(
        options.config,
        case_name=options.case_name,
        egrid=options.egrid,
        unrst=options.unrst,
        output_date=options.output_date,
        step=options.step,
    )
