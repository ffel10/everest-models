from everest_models.jobs.fm_ccs_dynamic.manager import main_entry_point

__all__ = ["main_entry_point"]

FULL_JOB_NAME = "CCS dynamic"

EXAMPLES = """

Argument examples
~~~~~~~~~~~~~~~~~

:code:`-c` example

.. code-block:: yaml

    fip_section:
      - fip_keyword: FIPNUM
        fipxxx_region:
          - fipxxx_number: 1
            output_name: output/dynamic_target.txt
            output_date: 2020-01-01
            keyword: FGPT

:code:`-cn` example

.. code-block:: text

    CASE_A
"""
