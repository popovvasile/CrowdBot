# from helper_funcs.lang_strings.strings import RUS, ENG

import json


# def check_dicts():
#     for key in ENG:
#         if key in RUS:
#             pass
#         else:
#             RUS[key]=ENG[key]
#     for key in RUS:
#         if key in ENG:
#             pass
#         else:
#             ENG[key]=RUS[key]
#     data = {"ENG": ENG,
#             "RUS": RUS}
#     with open('languages.json', 'w') as fp:
#         json.dump(data, fp, sort_keys=True, indent=4, ensure_ascii=False)

def check_strings():
    with open('languages.json', 'r') as f_in:
        lang_dict = json.load(f_in)

        for key in lang_dict["ENG"]:
            if key in lang_dict["RUS"]:
                continue
            else:
                lang_dict["RUS"][key] = lang_dict["ENG"][key]
        for key in lang_dict["RUS"]:
            if key in lang_dict["ENG"]:
                if lang_dict["RUS"][key].count("{}") != lang_dict["ENG"][key].count("{}"):
                    lang_dict["RUS"][key] = lang_dict["ENG"][key]
            else:
                lang_dict["ENG"][key] = lang_dict["RUS"][key]

        with open('languages2.json', 'w') as fp:
            json.dump(lang_dict, fp, sort_keys=True, indent=4, ensure_ascii=False)


check_strings()
