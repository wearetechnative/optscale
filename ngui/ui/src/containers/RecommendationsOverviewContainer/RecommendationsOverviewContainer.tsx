import { useCallback, useMemo, useState } from "react";
import { RecommendationModal } from "components/SideModalManager/SideModals";
import { useIsAllowed } from "hooks/useAllowedActions";
import { useGetIsRecommendationsDownloadAvailable } from "hooks/useGetIsRecommendationsDownloadAvailable";
import { useOpenSideModal } from "hooks/useOpenSideModal";
import { useOptscaleRecommendations } from "hooks/useOptscaleRecommendations";
import { ALL_SERVICES, useRecommendationServices } from "hooks/useRecommendationServices";
import { useRiSpExpensesSummary } from "hooks/useRiSpExpensesSummary";
import { useSyncQueryParamWithState } from "hooks/useSyncQueryParamWithState";
import OrganizationOptionsService from "services/OrganizationOptionsService";
import RecommendationsOverviewService from "services/RecommendationsOverviewService";
import {
  RECOMMENDATION_CATEGORY_QUERY_PARAMETER,
  RECOMMENDATION_SERVICE_QUERY_PARAMETER,
  RECOMMENDATION_VIEW_QUERY_PARAMETER,
} from "urls";
import { DEFAULT_RECOMMENDATIONS_FILTER, DEFAULT_VIEW, POSSIBLE_RECOMMENDATIONS_FILTERS, POSSIBLE_VIEWS } from "./Filters";
import RecommendationsOverview from "./RecommendationsOverview";
import BaseRecommendation from "./recommendations/BaseRecommendation";
import {
  setCategory as setCategoryActionCreator,
  setService as setServiceActionCreator,
  setView as setViewActionCreator,
} from "./redux/controlsState/actionCreators";
import { useControlState } from "./redux/controlsState/hooks";
import { VALUE_ACCESSORS } from "./redux/controlsState/reducer";

const OPTION_PREFIX = "recommendation_";
const DASHBOARD_HIDDEN_RECOMMENDATION_CARDS_OPTION = "dashboard_hidden_recommendation_cards";

type OrganizationOption = {
  name: string;
  value?: unknown;
};

const getStringArray = (value: unknown) =>
  Array.isArray(value) ? value.filter((item) => typeof item === "string") : [];

const getHiddenRecommendationTypes = (options: OrganizationOption[]): string[] => {
  const optionValue = options.find(({ name }) => name === DASHBOARD_HIDDEN_RECOMMENDATION_CARDS_OPTION)?.value;

  if (Array.isArray(optionValue)) {
    return getStringArray(optionValue);
  }

  if (typeof optionValue === "string") {
    try {
      return getStringArray(JSON.parse(optionValue));
    } catch {
      return [];
    }
  }

  if (
    typeof optionValue === "object" &&
    optionValue !== null &&
    "hiddenRecommendationTypes" in optionValue &&
    Array.isArray(optionValue.hiddenRecommendationTypes)
  ) {
    return getStringArray(optionValue.hiddenRecommendationTypes);
  }

  return [];
};

type RecommendationsOverviewContainerProps = {
  selectedDataSourceIds: string[];
  selectedDataSourceTypes: string[];
};

const RecommendationsOverviewContainer = ({
  selectedDataSourceIds,
  selectedDataSourceTypes,
}: RecommendationsOverviewContainerProps) => {
  const { useGet, useGetRecommendationsDownloadOptions, useUpdateOption, useCreateOption } =
    OrganizationOptionsService();
  const { options: downloadOptions } = useGetRecommendationsDownloadOptions();
  const { options } = useGet(true);
  const { updateOption, isUpdateOrganizationOptionLoading } = useUpdateOption();
  const { createOption, isCreateOrganizationOptionLoading } = useCreateOption();
  const isChangeRecommendationVisibilityAllowed = useIsAllowed({ requiredActions: ["EDIT_PARTNER"] });

  const downloadLimit = downloadOptions?.limit;

  const services = useRecommendationServices();

  const [category, setCategory] = useControlState({
    redux: { stateAccessor: VALUE_ACCESSORS.CATEGORY, actionCreator: setCategoryActionCreator },
    queryParamName: RECOMMENDATION_CATEGORY_QUERY_PARAMETER,
    defaultValue: DEFAULT_RECOMMENDATIONS_FILTER,
    possibleStates: POSSIBLE_RECOMMENDATIONS_FILTERS,
  });

  const [service, setService] = useControlState({
    redux: { stateAccessor: VALUE_ACCESSORS.SERVICE, actionCreator: setServiceActionCreator },
    queryParamName: RECOMMENDATION_SERVICE_QUERY_PARAMETER,
    defaultValue: ALL_SERVICES,
    possibleStates: Object.keys(services),
  });

  const [view, setView] = useControlState({
    redux: { stateAccessor: VALUE_ACCESSORS.VIEW, actionCreator: setViewActionCreator },
    queryParamName: RECOMMENDATION_VIEW_QUERY_PARAMETER,
    defaultValue: DEFAULT_VIEW,
    possibleStates: POSSIBLE_VIEWS,
  });

  const [search, setSearch] = useSyncQueryParamWithState({
    queryParamName: "search",
    defaultValue: "",
    searchParamsGetterOptions: {
      parseBooleans: false,
      parseNumbers: false,
    },
  });

  const { useGetOptimizationsOverview } = RecommendationsOverviewService();

  const { data, isDataReady } = useGetOptimizationsOverview(selectedDataSourceIds);

  const optscaleRecommendations = useOptscaleRecommendations();
  const storedHiddenRecommendationTypes = useMemo(() => getHiddenRecommendationTypes(options), [options]);
  const [hiddenRecommendationTypesOverride, setHiddenRecommendationTypesOverride] = useState<string[] | null>(null);
  const [isHiddenRecommendationCardsOptionCreated, setIsHiddenRecommendationCardsOptionCreated] = useState(false);
  const hiddenRecommendationTypes = hiddenRecommendationTypesOverride ?? storedHiddenRecommendationTypes;
  const isRecommendationVisibilityUpdateLoading = isUpdateOrganizationOptionLoading || isCreateOrganizationOptionLoading;
  const hiddenRecommendationCardsOptionExists = options.some(
    ({ name }: { name: string }) => name === DASHBOARD_HIDDEN_RECOMMENDATION_CARDS_OPTION
  ) || isHiddenRecommendationCardsOptionCreated;

  const updateHiddenRecommendationTypes = useCallback(
    (nextHiddenRecommendationTypes: string[]) => {
      setHiddenRecommendationTypesOverride(nextHiddenRecommendationTypes);

      const save = hiddenRecommendationCardsOptionExists ? updateOption : createOption;

      save(DASHBOARD_HIDDEN_RECOMMENDATION_CARDS_OPTION, { hiddenRecommendationTypes: nextHiddenRecommendationTypes });
      setIsHiddenRecommendationCardsOptionCreated(true);
    },
    [createOption, hiddenRecommendationCardsOptionExists, updateOption]
  );

  const organizationRecommendationOptions = options
    .filter(({ name }: { name: string }) =>
      /**
       * The options API has 2 output formats: an array of names ([string]) and an array of objects ([{name, value}]).
       * On the "Org options" page, we request options with withValues set to false, giving us an array of strings.
       * However, on the Recommendations page, when trying to access the "name" property, it's undefined, resulting in a "cannot read property" error.
       * Adding `?.` fixes OS-6409
       */
      name?.startsWith(OPTION_PREFIX)
    )
    .reduce((result, { name, value }) => ({ ...result, [name.slice(OPTION_PREFIX.length)]: value }), {});

  const openSideModal = useOpenSideModal();

  const onRecommendationClick = useCallback(
    (recommendation: BaseRecommendation) => {
      openSideModal(RecommendationModal, {
        type: recommendation.type,
        titleMessageId: recommendation.title,
        limit: downloadLimit,
        dataSourceIds: selectedDataSourceIds,
        dismissible: recommendation.dismissible,
        withExclusions: recommendation.withExclusions,
      });
    },
    [downloadLimit, openSideModal, selectedDataSourceIds]
  );

  const { isLoading: isRiSpExpensesSummaryLoading, summary: riSpExpensesSummary } =
    useRiSpExpensesSummary(selectedDataSourceIds);

  const { isLoading: isGetIsDownloadAvailableLoading, isDownloadAvailable } = useGetIsRecommendationsDownloadAvailable();

  return (
    <RecommendationsOverview
      lastCompleted={data.last_completed}
      totalSaving={data.total_saving}
      nextRun={data.next_run}
      lastRun={data.last_run}
      isDataReady={isDataReady}
      onRecommendationClick={onRecommendationClick}
      setCategory={setCategory}
      category={category}
      setSearch={setSearch}
      search={search}
      setView={setView}
      view={view}
      setService={setService}
      service={service}
      recommendationsData={{ ...data, organizationOptions: organizationRecommendationOptions }}
      recommendationClasses={optscaleRecommendations}
      hiddenRecommendationTypes={hiddenRecommendationTypes}
      onRecommendationVisibilityChange={updateHiddenRecommendationTypes}
      isRecommendationVisibilityUpdateLoading={isRecommendationVisibilityUpdateLoading}
      isChangeRecommendationVisibilityAllowed={isChangeRecommendationVisibilityAllowed}
      downloadLimit={downloadLimit}
      riSpExpensesSummary={riSpExpensesSummary}
      isRiSpExpensesSummaryLoading={isRiSpExpensesSummaryLoading}
      isDownloadAvailable={isDownloadAvailable}
      isGetIsDownloadAvailableLoading={isGetIsDownloadAvailableLoading}
      selectedDataSourceIds={selectedDataSourceIds}
      selectedDataSourceTypes={selectedDataSourceTypes}
    />
  );
};

export default RecommendationsOverviewContainer;
