import json
from base64 import urlsafe_b64decode, urlsafe_b64encode
from typing import Any, Callable, Self

import pydantic


class Cursor(pydantic.BaseModel):
    """
    A cursor object that the client is expected to store and provide in the
    next request to get the next batch of changes.
    """

    # Which transaction are we at
    xid_at: int | None = None
    # Which item within that transaction are we at
    xid_at_id: int | None = None
    # Transactions in progress
    xip_list: list[int]
    # Next transaction ID
    xid_next: int

    @pydantic.model_serializer(mode="wrap", when_used="json")
    def base64_encode(
        self,
        handler: Callable[[Self, pydantic.SerializationInfo], Any],
        info: pydantic.SerializationInfo,
    ) -> Any:
        """
        Serialize to a base64 blob when encoding to JSON.
        """

        data = handler(self, info)
        return urlsafe_b64encode(json.dumps(data).encode()).decode("ascii")

    @pydantic.model_validator(mode="wrap")
    def base64_decode(
        cls,
        value: Any,
        handler: Callable[[Any], Self],
        info: pydantic.ValidationInfo,
    ) -> Self:
        """
        Decode from base64 when validating from JSON.
        """

        if info.mode == "json":
            value = urlsafe_b64decode(value)
            value = json.loads(value)
        return handler(value)

    def next_cursor(
        self,
        *,
        snapshot: "Snapshot",
        last_modified_txid: int | None,
        last_object_id: int | None,
        has_more: bool
    ) -> Self:
        """
        Get the next cursor
        """

        # We did not fill the batch, so we know we're done with anything not
        # still in progress (as of the snapshot we got, of course)
        if not has_more:
            # The last row we got happens to be the xmax, so xmax can't be some
            # in-progress transaction, so skip past it so we don't get these
            # rows again on the next >= comparison
            xid_next = snapshot.xmax
            if last_modified_txid == xid_next:
                xid_next += 1

            xip_list = [xip for xip in snapshot.xip_list if xip < xid_next]

            return self.__class__(xid_next=xid_next, xip_list=xip_list)

        assert last_modified_txid
        assert last_object_id

        xid_at = last_modified_txid

        # When we're done scrolling through seqs for this txid, then + 1 is
        # where we'll go next. Unless we've been brought back in time
        # (via a xip_list), which the max further down guards against
        xid_next = xid_at + 1

        # xid_next should never go backwards. The last item in a batch might
        # have been contributed by an old xip (which could in turn have become
        # an xid_at). This makes sure we can't be tricked back. If another old
        # transaction has committed and has changes now visible, we'll get to
        # them via the xip_list check, not via last_modified_txid >= xid_next
        xid_next = max(self.xid_next, xid_next)

        if xid_at == snapshot.xmax:
            # xmax happens to be something we just saw.
            # Move past it, so we don't keep getting the same rows back until
            # something else progresses xmax.
            xid_next = xid_at + 1
        else:
            # Unless we just saw xmax ourselves, don't move past it. It could
            # be another transaction in progress.
            xid_next = min(xid_next, snapshot.xmax)

        if self.xid_at == xid_at:
            # If xid_at did not move, then nothing from the xip_list
            # have been processed
            xips_to_keep = self.xip_list
        else:
            # If it did move, then at least some xip_list txids have been
            # involved, and we don't need to retain anything less than xid_at,
            # unless they're still in the snapshot, which get union-ed below.
            # Now-committed txids from xip_list are processed in order, and the
            # last one will become the new xid_at if we don't process all the changes.
            xips_to_keep = [xip for xip in self.xip_list if xip > xid_at]

        # We obviously have to carry forward what's still in the snapshot:
        xip_list = list(set(snapshot.xip_list) | set(xips_to_keep))

        return self.__class__(
            xid_next=xid_next,
            xid_at=xid_at,
            xid_at_id=last_object_id,
            xip_list=xip_list,
        )


class Snapshot(pydantic.BaseModel):
    """
    A snapshot of the currently active transactions
    """

    # xmin is the lowest visible txid
    xmin: int
    # ... while xmax is the highest
    xmax: int
    # ... and "xip" is "transactions in progress"
    xip_list: list[int]

    # In general, the modifications of a transaction is visible iff
    # xmin <= txid < xmax and txid not in xip_list
