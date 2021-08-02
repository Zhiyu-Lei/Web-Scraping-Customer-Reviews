import pandas as pd


def df2excel(df: pd.DataFrame, output: str) -> str:
    version = 0
    while True:
        file_name = "outputs/" + output + str(version) + ".xlsx" if version else "outputs/" + output + ".xlsx"
        try:
            df.to_excel("outputs/" + output + ".xlsx", header=True, index=False)
            break
        except PermissionError:
            version += 1
    return file_name
