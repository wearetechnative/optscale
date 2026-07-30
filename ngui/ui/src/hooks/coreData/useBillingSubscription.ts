import { useBillingSubscriptionQuery } from "graphql/__generated__/hooks/restapi";
import { useOrganizationInfo } from "../useOrganizationInfo";

export const useBillingSubscription = () => {
  const { organizationId } = useOrganizationInfo();

  const { data: { billingSubscription } = {} } = useBillingSubscriptionQuery({
    variables: {
      organizationId,
    },
    fetchPolicy: "cache-only",
    // Suppress GraphQL errors (e.g., 403 Forbidden for users without billing permissions)
    errorPolicy: "ignore",
  });

  return billingSubscription;
};
