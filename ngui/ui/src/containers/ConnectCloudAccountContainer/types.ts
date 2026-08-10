export type Config = {
  linked?: boolean;
  assume_role_account_id?: string;
  assume_role_name?: string;
  csv_file?: File;
  [key: string]: any;
};

export type Params = {
  name: string;
  type: string;
  config: Config;
};
