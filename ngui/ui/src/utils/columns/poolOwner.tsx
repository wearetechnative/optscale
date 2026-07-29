import { FormattedMessage } from "react-intl";
import PoolLabel from "components/PoolLabel";
import TextWithDataTestId from "components/TextWithDataTestId";

const poolOwner = ({ headerDataTestId, id }) => ({
  header: (
    <TextWithDataTestId dataTestId={headerDataTestId}>
      <FormattedMessage id="pool" />
    </TextWithDataTestId>
  ),
  id,
  style: {
    whiteSpace: "nowrap",
  },
  cell: ({ row: { original } }) =>
    original.owner || original.pool ? (
      // Owner data is kept but not displayed
      original.pool.id && <PoolLabel id={original.pool.id} name={original.pool.name} type={original.pool.purpose} />
    ) : null,
});

export default poolOwner;
