from django.db.migrations import RunSQL

CREATE_TXID_OFFSET_FUNCTION_SQL = """\
CREATE OR REPLACE FUNCTION txid_offset()
RETURNS bigint
STABLE LEAKPROOF PARALLEL SAFE
LANGUAGE SQL AS
$$ SELECT 0::bigint $$;
"""

DROP_TXID_OFFSET_FUNCTION_SQL = "DROP FUNCTION IF EXISTS txid_offset();"


class CreateTxidOffsetFunction(RunSQL):

    def __init__(self) -> None:
        super().__init__(
            sql=CREATE_TXID_OFFSET_FUNCTION_SQL,
            reverse_sql=DROP_TXID_OFFSET_FUNCTION_SQL,
        )


CREATE_ADJUSTED_TXID_CURRENT_FUNCTION_SQL = """\
CREATE OR REPLACE FUNCTION adjusted_txid_current()
RETURNS bigint
STABLE LEAKPROOF
LANGUAGE SQL AS
$$ SELECT txid_offset() + txid_current() $$;
"""

DROP_ADJUSTED_TXID_FUNCTION_SQL = "DROP FUNCTION IF EXISTS adjusted_txid_current();"


class CreateAdjustedTxidCurrentFunction(RunSQL):

    def __init__(self) -> None:
        super().__init__(
            sql=CREATE_ADJUSTED_TXID_CURRENT_FUNCTION_SQL,
            reverse_sql=DROP_ADJUSTED_TXID_FUNCTION_SQL,
        )
