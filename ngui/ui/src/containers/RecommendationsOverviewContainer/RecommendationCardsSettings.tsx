import SettingsOutlinedIcon from "@mui/icons-material/SettingsOutlined";
import { Box, Checkbox, Divider, FormControlLabel, FormGroup, Typography } from "@mui/material";
import { FormattedMessage } from "react-intl";
import Button from "components/Button";
import IconButton from "components/IconButton";
import Popover from "components/Popover";
import BaseRecommendation from "./recommendations/BaseRecommendation";

type RecommendationCardsSettingsProps = {
  recommendations: BaseRecommendation[];
  hiddenRecommendationTypes: string[];
  onChange: (hiddenRecommendationTypes: string[]) => void;
  isLoading: boolean;
  isChangeSettingsAllowed: boolean;
};

const RecommendationCardsSettings = ({
  recommendations,
  hiddenRecommendationTypes,
  onChange,
  isLoading,
  isChangeSettingsAllowed,
}: RecommendationCardsSettingsProps) => {
  const toggleRecommendation = (type: string) => {
    const nextHiddenRecommendationTypes = hiddenRecommendationTypes.includes(type)
      ? hiddenRecommendationTypes.filter((hiddenType) => hiddenType !== type)
      : [...hiddenRecommendationTypes, type];

    onChange(nextHiddenRecommendationTypes);
  };

  return (
    <Popover
      disabled={!isChangeSettingsAllowed}
      label={
        <IconButton
          icon={<SettingsOutlinedIcon />}
          dataTestId="btn_recommendation_cards_settings"
          disabled={!isChangeSettingsAllowed}
          tooltip={{
            show: true,
            messageId: isChangeSettingsAllowed ? "recommendationCardsSettings" : "youDoNotHaveEnoughPermissions",
          }}
        />
      }
      renderMenu={() => (
        <Box width={360} maxHeight={520} overflow="auto" padding={1}>
          <Box paddingX={1} paddingY={0.5}>
            <Typography variant="subtitle2">
              <FormattedMessage id="recommendationCardsSettings" />
            </Typography>
          </Box>
          <Divider />
          <FormGroup>
            {recommendations.map((recommendation) => {
              const checked = !hiddenRecommendationTypes.includes(recommendation.type);

              return (
                <FormControlLabel
                  key={recommendation.type}
                  control={
                    <Checkbox
                      checked={checked}
                      onChange={() => toggleRecommendation(recommendation.type)}
                      disabled={isLoading}
                      data-test-id={`checkbox_recommendation_card_${recommendation.type}`}
                    />
                  }
                  label={<FormattedMessage id={recommendation.title} />}
                />
              );
            })}
          </FormGroup>
          <Divider />
          <Box display="flex" justifyContent="flex-end" paddingTop={1}>
            <Button
              messageId="enableAllRecommendationCards"
              variant="text"
              onClick={() => onChange([])}
              disabled={isLoading || hiddenRecommendationTypes.length === 0}
              dataTestId="btn_enable_all_recommendation_cards"
            />
          </Box>
        </Box>
      )}
    />
  );
};

export default RecommendationCardsSettings;
