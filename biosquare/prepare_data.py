import pandas as pd
import os

def convert_data(df):
    tmp = {}
    other = {}
    
    # Check if 'target_name' exists, if not, it might already be wide or in a different format
    if "target_name" not in df.columns:
        print("Warning: 'target_name' column not found. Assuming data is already in wide format or structure is different.")
        return df

    ll = df["target_name"].unique().tolist()
    
    # Identify key columns. 'target' might not exist in test set.
    cols_to_use = ["image_path", "target_name"]
    if "target" in df.columns:
        cols_to_use.append("target")
    
    # Static columns that are the same for each image_path
    static_cols = ["Species", "State", "Sampling_Date"]
    existing_static_cols = [c for c in static_cols if c in df.columns]
    
    # Iterate through the dataframe
    # We use a dictionary for fast lookups
    # Group by image_path
    
    df_grouped = df.groupby('image_path')
    
    new_data = []
    
    for image_path, group in df_grouped:
        row = {'id': image_path}
        
        # Add static info
        if existing_static_cols:
             # Just take the first value as they should be identical for the same image
            first_row = group.iloc[0]
            for col in existing_static_cols:
                row[col] = first_row[col]
        
        # Add targets
        for index, r in group.iterrows():
            target_name = r['target_name']
            if 'target' in r:
                row[target_name] = r['target']
            else:
                 # For test set, we just want to know which targets exist/are requested, 
                 # but for a wide format, we simply need the image path. 
                 # The submission format is long, so we will need to pivot back later.
                 # For inference, wide format is easier to handle (one image -> multiple preds).
                 pass
        
        new_data.append(row)

    new_data = pd.DataFrame(new_data)
    return new_data

def main():
    datasets_dir = "../" # Assuming we are in CSIRO-Image2Biomass-main and csvs are in parent or current
    # Ideally search for train.csv and test.csv
    
    # Adjust path as per user environment
    # The user said "la carpeta de entrenamiento es train en este folder y train.csv y tambien test y test.csv"
    # So they are likely in the current directory or a 'dataset' subdirectory relative to the root of the provided folder.
    # But based on `ls` output earlier, we are in `CSIRO-Image2Biomass-main`. 
    # The user said "en este folder" referring to `CSIRO-Image2Biomass-main` or the parent `csiro-biomass`.
    # Let's check typical locations.
    
    potential_paths = [".", "..", "./datasets"]
    
    train_path = None
    test_path = None
    
    for p in potential_paths:
        if os.path.exists(os.path.join(p, "train.csv")):
            train_path = os.path.join(p, "train.csv")
        if os.path.exists(os.path.join(p, "test.csv")):
            test_path = os.path.join(p, "test.csv")
    
    if train_path:
        print(f"Found train.csv at {train_path}")
        df_train = pd.read_csv(train_path)
        df_train_wide = convert_data(df_train)
        output_train = "train_wide.csv"
        df_train_wide.to_csv(output_train, index=False)
        print(f"Saved wide format train data to {output_train}")
        
    if test_path:
        print(f"Found test.csv at {test_path}")
        df_test = pd.read_csv(test_path)
        # For test, the 'target' column might be missing or we might want to preserve the structure to pivot back.
        # convert_data handles missing 'target'.
        df_test_wide = convert_data(df_test)
        output_test = "test_wide.csv"
        df_test_wide.to_csv(output_test, index=False)
        print(f"Saved wide format test data to {output_test}")

if __name__ == "__main__":
    main()
