import { FormattedMessage } from "react-intl";
import PoolLabel from "components/PoolLabel";
import TextWithDataTestId from "components/TextWithDataTestId";

const poolAndOwner = ({ headerDataTestId }) => ({
  header: (
    <TextWithDataTestId dataTestId={headerDataTestId}>
      <FormattedMessage id="pool" />
    </TextWithDataTestId>
  ),
  id: "pool/owner",
  style: {
    whiteSpace: "nowrap",
  },
  cell: ({
    row: {
      original: { pool: { id: poolId, name: poolName, purpose: poolPurpose } = {} },
    } = {},
  }) => (
    // Owner data is kept but not displayed
    <PoolLabel id={poolId} name={poolName} type={poolPurpose} />
  ),
});

export default poolAndOwner;
