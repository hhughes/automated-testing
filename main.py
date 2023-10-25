import json
import sys
import llm


def debug(o):
    for line in o.split("\n"):
        print(f"DEBUG: {line}")

def readstdin():
    result = ""
    for line in sys.stdin.readlines():
        result += line
    return result

def prompt(model, input):
    p = f'[INST] {input} [/INST]' if model.model_id.find("instruct") != -1 else input
    debug(f"******Prompt******\n{p}\n******************")
    # r = model.prompt(p, max_tokens=4096, temperature=0.5, repeat_penalty=1.1, n_gpu_layers=16).text()
    r = model.prompt(p, max_tokens=4096, temperature=0.5, repeat_penalty=1.1, n_gpu_layers=16).text()
    debug(f"******Response******\n{r}\n******************")
    return r

def prompt_json(model, input, format):
    for i in range(5):
        try:
            result = prompt(model, f'''{input} Respond only in json format: {format}.
Do not start with any preamble like "Here is an example..." or "Sure, here are...". Make sure to use correct json syntax such as "null" for None values.''')
            first_valid_json = len(result)
            for c in ['"', '{', '[']:
                i = result.find(c)
                if i >= 0:
                    first_valid_json = min(first_valid_json, i)
            return json.loads(result[first_valid_json:])
        except ValueError:
            print("did not return properly formatted result, re-running")
    raise "could not get json-formatted response from query"

def prompt_code(model, input, lang):
    for i in range(5):
        result = prompt(model, f'''{input}
Only respond with valid Python code that represents the test-case, surrounded by ```. Do not respond with any preamble or words after the test implementation.''')
        code_start = result.find('```')
        if code_start < 0:
            print('could not find code start')
            continue
        code_end = result.find('```', code_start + 3)
        if code_end < 0:
            print('could not find code end')
            continue
        return result[code_start+3:code_end]
    raise "could not valid code response from query"

if __name__ == '__main__':
    '''
    - read code from the command-line
    - extract functions (names, parameters and descriptions)
    - write test cases for each functions
    - execute test cases
    - determine bugs?
    '''

    lang = "Python"
    input_code = readstdin()

    # run the code to load the method defined
    exec(input_code)

    model = llm.get_model("codellama-instr-13b-q5")
    #model = llm.get_model("codellama-13b-q5")
    functions = prompt_json(model, f"""Here is some {lang} code:
{input_code}
Find all the function names defined in the code above.""", """array of json dictionaries. Each object should have the following keys:
- function_name: the name of the function
- function_description: concise description of the function
- function_input_parameters: array of tuples where the first element is the tuple is the name of the function parameter and the second element is the type of the function parameter
- function_result_type: the type of the return value of the function
Ignore any classes or methods defined inside classes.""")
    for function in functions:
        tests = prompt_json(model, f"""Here is some {lang} code:
{input_code}
Describe up to five test cases which could be used to validate functionality or bounds for the function named '{function["function_name"]}' above. Each test case should be a concise description of no more than 50 words and contain no code.""", f"""array of json dictionaries. Each object should have the following keys:
- test_case_name: the name of the test case, this should describe the test case in no more than 5 words, contain no spaces and be in snake-case
- test_case_description: a succinct description of the test case
- test_input: the list of input {function["function_input_parameters"]} for this test case, where the second item in each input value pair is a string that represents a value in python
- test_expected_output: the expected output of the '{function["function_name"]}' function in the correct type {function["function_result_type"]}""")
        for test in tests:
            """Here is a description of a function in json format:
{json.dumps(function)}
Where "name" is the name of the function, "description" is a description of its purpose, "input_parameters" is a list where each value is a list that represents one of the functions parameters, the first element is the name of the parameter and the second is its type, and "result_type" is the type returned by the function."""
            code = prompt_code(model, f"""Here is a description of a test case for a function '{function["function_name"]}':
{json.dumps(test)}
Where "test_case_name" is the name of the test, "test_case_description" is a description of what the test is trying to do, "test_input" are the inputs that should be provided to the function '{function["function_name"]}' and "test_expected_output" is the expected result of the function call with the provided parameters.
Write a single Python test case function which executes function '{function["function_name"]}' using the test_input provided in the test-case json and asserts the result is equal to the test_expected_output in the test-case json. Use the test_case_name from the test-case json as the name the function. Do not encapsulate the test in a class. Do not include a definition or function stub for '{function["function_name"]}'. Do not print any code except the test-case function.""", lang)

            try:
                print(f'Loading code for {test["test_case_name"]}...')
                exec(code)
                print(f'Running test {test["test_case_name"]}...')
                exec(f'{test["test_case_name"]}()')
                print("Success!")
            except Exception as e:
                print(f'Failed: {e}')


