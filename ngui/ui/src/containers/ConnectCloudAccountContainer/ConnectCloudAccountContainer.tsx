import { useNavigate } from "react-router-dom";
import { useState } from "react";
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
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [isUploading, setIsUploading] = useState<boolean>(false);

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
    console.log('onSubmit called with:', { name, config, type });
    trackEvent({ category: GA_EVENT_CATEGORIES.DATA_SOURCE, action: "Try connect", label: type });

    // Handle CSV upload via REST API with FormData and progress tracking
    if (type === CSV_UPLOAD) {
      console.log('CSV_UPLOAD detected');
      console.log('config.csv_file:', config.csv_file);

      if (!config.csv_file) {
        console.error('No CSV file provided');
        alert('Please select a CSV file to upload');
        return;
      }

      const formData = new FormData();
      formData.append('name', name);
      formData.append('type', type);
      formData.append('csv_file', config.csv_file);

      setIsUploading(true);
      setUploadProgress(0);

      return new Promise<void>((resolve, reject) => {
        const xhr = new XMLHttpRequest();

        // Track upload progress
        xhr.upload.addEventListener('progress', (event) => {
          if (event.lengthComputable) {
            const percentComplete = Math.round((event.loaded / event.total) * 100);
            setUploadProgress(percentComplete);
            console.log(`Upload progress: ${percentComplete}%`);
          }
        });

        // Handle completion
        xhr.addEventListener('load', () => {
          setIsUploading(false);
          if (xhr.status >= 200 && xhr.status < 300) {
            console.log('CSV upload successful');
            refetch([GET_AVAILABLE_FILTERS]);
            redirectToCloudsOverview();
            resolve();
          } else {
            console.error('CSV upload failed:', xhr.status, xhr.statusText);
            let errorMessage = 'Failed to upload CSV file';
            try {
              const error = JSON.parse(xhr.responseText);
              errorMessage = error.error?.reason || errorMessage;
            } catch (e) {
              // Ignore JSON parse error
            }
            alert(`CSV upload failed: ${errorMessage}`);
            reject(new Error(errorMessage));
          }
        });

        // Handle errors
        xhr.addEventListener('error', () => {
          setIsUploading(false);
          console.error('CSV upload network error');
          alert('CSV upload failed: Network error');
          reject(new Error('Network error'));
        });

        // Handle abort
        xhr.addEventListener('abort', () => {
          setIsUploading(false);
          console.log('CSV upload aborted');
          reject(new Error('Upload aborted'));
        });

        // Open and send request
        xhr.open('POST', `/restapi/v2/organizations/${organizationId}/cloud_accounts`);
        xhr.withCredentials = true;
        xhr.send(formData);
      });
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

  return (
    <ConnectCloudAccount
      isLoading={loading || isUploading}
      uploadProgress={isUploading ? uploadProgress : undefined}
      onSubmit={onSubmit}
      onCancel={redirectToCloudsOverview}
    />
  );
};

export default ConnectCloudAccountContainer;
