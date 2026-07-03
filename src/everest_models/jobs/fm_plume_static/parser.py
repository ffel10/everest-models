from everest_models.jobs.shared.arguments import bootstrap_parser, get_parser
from everest_models.jobs.shared.validators import valid_input_file

CONFIG_ARGUMENT = "-c/--config"
CASE_NAME_ARGUMENT = "-cn/--case-name"


@bootstrap_parser
def build_argument_parser(skip_type=False):
    parser, required_group = get_parser(
        description=(
            "Extract static plume targets from UNSMRY using a YAML configuration."
        )
    )
    required_group.add_argument(
        *CONFIG_ARGUMENT.split("/"),
        required=True,
        type=valid_input_file if not skip_type else str,
        help="Path to plume static YAML configuration file.",
    )
    required_group.add_argument(
        *CASE_NAME_ARGUMENT.split("/"),
        required=True,
        help="Case base path used to resolve CASE.UNSMRY.",
    )
    return parser
