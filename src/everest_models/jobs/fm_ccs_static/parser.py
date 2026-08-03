from pathlib import Path

from everest_models.jobs.shared.arguments import bootstrap_parser, get_parser


@bootstrap_parser
def build_argument_parser(skip_type: bool = False):
    parser, required_group = get_parser(
        description="Extract static plume targets from UNSMRY using a YAML config."
    )
    required_group.add_argument(
        "-c",
        "--config",
        required=True,
        type=Path if not skip_type else str,
        help="Path to plume static config YAML.",
    )
    required_group.add_argument(
        "-cn",
        "--case_name",
        required=True,
        type=Path if not skip_type else str,
        help="Case base path (accepted for workflow compatibility).",
    )
    return parser