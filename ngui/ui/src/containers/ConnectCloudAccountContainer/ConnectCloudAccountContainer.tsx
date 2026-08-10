import { useNavigate } from "react-router-dom";
import { GET_AVAILABLE_FILTERS } from "api/restapi/actionTypes";
import ConnectCloudAccount from "components/ConnectCloudAccount";
import { DataSourcesDocument, useCreateDataSourceMutation } from "graphql/__generated__/hooks/restapi";
import { useOrganizationInfo } from "hooks/useOrganizationInfo";
import { useRefetchApis } from "hooks/useRefetchApis";
import { CLOUD_ACCOUNTS } from "urls";
import { trackEvent, GA_EVENT_CATEGORIES } from "utils/analytics";
import {
  ALIBABA_CNR,
  AWS_CNR,
  AZURE_CNR,
  AZURE_TENANT,
  DATABRICKS,
  GCP_CNR,
  GCP_TENANT,
  KUBERNETES_CNR,
  NEBIUS,
  CSV_UPLOAD,
} from "utils/constants";
import type { Config, Params } from "./types";

const ConnectCloudAccountContainer = () => {
  const { organizationId } = useOrganizationInfo();

  const refetch = useRefetchApis();

  const navigate = useNavigate();

  const [createDataSource, { loading }] = useCreateDataSourceMutation();

  const redirectToCloudsOverview = () => navigate(CLOUD_ACCOUNTS);

  const getAwsConfigName = (config: Config) => {
    if (config.assume_role_account_id && config.assume_role_name) {
      return "awsAssumedRoleConfig";
    }

    if (config.linked) {
      return "awsLinkedConfig";
    }

    return "awsRootConfig";
  };

  const onSubmit = async ({ name, config, type }: Params) => {
    trackEvent({ category: GA_EVENT_CATEGORIES.DATA_SOURCE, action: "Try connect", label: type });

    // Handle CSV upload via REST API with FormData
    if (type === CSV_UPLOAD) {
      const formData = new FormData();
      formData.append('name', name);
      formData.append('type', type);
      formData.append('csv_file', config.csv_file);

      try {
        const response = await fetch(`/restapi/v2/organizations/${organizationId}/cloud_accounts`, {
          method: 'POST',
          body: formData,
          credentials: 'include',
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.error?.reason || 'Failed to upload CSV file');
        }

        refetch([GET_AVAILABLE_FILTERS]);
        redirectToCloudsOverview();
      } catch (error) {
        console.error('CSV upload failed:', error);
        const errorMessage = error instanceof Error ? error.message : 'Unknown error';
        alert(`CSV upload failed: ${errorMessage}`);
      }
      return;
    }

    // Handle other cloud types via GraphQL
    const configName = {
      [AWS_CNR]: getAwsConfigName(config),
      [AZURE_TENANT]: "azureTenantConfig",
      [AZURE_CNR]: "azureSubscriptionConfig",
      [GCP_CNR]: "gcpConfig",
      [GCP_TENANT]: "gcpTenantConfig",
      [ALIBABA_CNR]: "alibabaConfig",
      [NEBIUS]: "nebiusConfig",
      [DATABRICKS]: "databricksConfig",
      [KUBERNETES_CNR]: "k8sConfig",
    }[type];

    createDataSource({
      variables: {
        organizationId,
        params: {
          name,
          type,
          [configName]: config,
        },
      },
      refetchQueries: [DataSourcesDocument],
    }).then(() => {
      refetch([GET_AVAILABLE_FILTERS]);
      redirectToCloudsOverview();
    });
  };

  return <ConnectCloudAccount isLoading={loading} onSubmit={onSubmit} onCancel={redirectToCloudsOverview} />;
};

export default ConnectCloudAccountContainer;
