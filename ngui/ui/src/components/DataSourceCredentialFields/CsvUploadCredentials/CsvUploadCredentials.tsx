import { Controller, useFormContext } from "react-hook-form";
import { FormattedMessage, useIntl } from "react-intl";
import FormHelperText from "@mui/material/FormHelperText";
import Typography from "@mui/material/Typography";
import { Dropzone } from "components/Dropzone";

export const FIELD_NAMES = Object.freeze({
  CSV_FILE: "csv_file",
});

const CsvUploadCredentials = () => {
  const { control, formState: { errors } } = useFormContext();
  const intl = useIntl();

  return (
    <>
      <Typography variant="body2" gutterBottom>
        <FormattedMessage id="csvUploadDescription" />
      </Typography>
      <Controller
        name={FIELD_NAMES.CSV_FILE}
        control={control}
        rules={{
          validate: {
            isFile: (value) => {
              if (!value) {
                return intl.formatMessage({ id: "thisFieldIsRequired" });
              }
              return true;
            },
          },
        }}
        render={({ field: { onChange, value } }) => (
          <Dropzone
            acceptedFiles={[".csv", "text/csv", "application/vnd.ms-excel"]}
            messageId="dropOrSelectCsvFile"
            errorMessageId={errors[FIELD_NAMES.CSV_FILE]?.message as string}
            onChange={(files) => {
              if (files && files.length > 0) {
                onChange(files[0]);
              }
            }}
          />
        )}
      />
      {errors[FIELD_NAMES.CSV_FILE] && (
        <FormHelperText error>
          {errors[FIELD_NAMES.CSV_FILE].message}
        </FormHelperText>
      )}
    </>
  );
};

export default CsvUploadCredentials;
