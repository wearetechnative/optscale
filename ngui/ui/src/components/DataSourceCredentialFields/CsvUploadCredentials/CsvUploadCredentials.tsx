import { Controller, useFormContext } from "react-hook-form";
import { FormattedMessage } from "react-intl";
import FormHelperText from "@mui/material/FormHelperText";
import Typography from "@mui/material/Typography";
import { Dropzone } from "components/Dropzone";

export const FIELD_NAMES = Object.freeze({
  CSV_FILE: "csvFile",
});

const CsvUploadCredentials = () => {
  const { control, formState: { errors } } = useFormContext();

  return (
    <>
      <Typography variant="body2" gutterBottom>
        <FormattedMessage id="csvUploadDescription" />
      </Typography>
      <Controller
        name={FIELD_NAMES.CSV_FILE}
        control={control}
        rules={{
          required: {
            value: true,
            message: <FormattedMessage id="thisFieldIsRequired" />,
          },
        }}
        render={({ field: { onChange } }) => (
          <Dropzone
            acceptedFiles={[".csv", "text/csv", "application/vnd.ms-excel"]}
            messageId="dropOrSelectCsvFile"
            errorMessageId={errors[FIELD_NAMES.CSV_FILE]?.message}
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
