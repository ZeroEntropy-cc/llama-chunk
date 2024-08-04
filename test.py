from llama_cpp import Llama
import math
import random
import json
import numpy as np

prompt_format = """
<|start_header_id|>system<|end_header_id|>

{SYSTEM_MESSAGE}
<|eot_id|><|start_header_id|>user<|end_header_id|>

{EXAMPLE_INPUT}
<|eot_id|><|start_header_id|>assistant<|end_header_id|>

{EXAMPLE_OUTPUT}
<|eot_id|><|start_header_id|>user<|end_header_id|>

{USER_MESSAGE}
<|eot_id|><|start_header_id|>assistant<|end_header_id|>
""".strip() + "\n\n"

llm = Llama(
    model_path="./models/Meta-Llama-3.1-70B-Instruct-Q6_K_L-00001-of-00002.gguf",
    #grammar=LlamaGrammar.from_file("./dictionary_clean.gbnf"),
    logits_all=True,
    n_ctx=8192,
    n_gpu_layers=-1,
)

# Get vocab
vocab = []
for i in range(llm.n_vocab()):
    token: str | None
    try:
        token = llm.detokenize([i]).decode("utf-8")
    except UnicodeDecodeError:
        token = None
    vocab.append(token)

BIG_SPLIT_TOKEN = "\u6bb5"
SMALL_SPLIT_TOKEN = "\u987f"

BIG_SPLIT_TOKEN_INDEX = None
for i, vocab_element in enumerate(vocab):
    if vocab_element == BIG_SPLIT_TOKEN:
        BIG_SPLIT_TOKEN_INDEX = i
assert BIG_SPLIT_TOKEN_INDEX != None

def replace_split_tokens(text: str) -> str:
    return text.replace("{SPLIT_TOKEN}", BIG_SPLIT_TOKEN)
    return text.replace("{BIG_SPLIT_TOKEN}", BIG_SPLIT_TOKEN).replace("{SMALL_SPLIT_TOKEN}", SMALL_SPLIT_TOKEN)

SYSTEM_MESSAGE = replace_split_tokens(open("system.txt").read())
EXAMPLE_INPUT = open("example_input.txt").read()
EXAMPLE_OUTPUT = replace_split_tokens(open("example_output.txt").read())
USER_MESSAGE = open("user2.txt").read()
USER_MESSAGE = open("userhtml.txt").read().replace("\n", "")
USER_MESSAGE = open("userbenchmarksmall.txt").read()
USER_MESSAGE = open("userbenchmark.txt").read()

# null_state = llm.save_state()
input_string = prompt_format.format(
    SYSTEM_MESSAGE=SYSTEM_MESSAGE,
    EXAMPLE_INPUT=EXAMPLE_INPUT,
    EXAMPLE_OUTPUT=BIG_SPLIT_TOKEN + EXAMPLE_OUTPUT,
    USER_MESSAGE=USER_MESSAGE,
)
input_tokens = llm.tokenize(input_string.encode("utf-8"), special=True) + llm.tokenize(BIG_SPLIT_TOKEN.encode("utf-8"))
user_tokens = llm.tokenize(USER_MESSAGE.encode("utf-8"))
print(f"NUM PREFIX TOKENS: {len(input_tokens)}")
print("Evaluating prefix tokens...")
llm.eval(input_tokens)
start_n_tokens = llm.n_tokens
start_index = len(input_tokens)
print("Done!")

def get_common_prefix_length(prefix_user_tokens):
    for i in range(len(prefix_user_tokens)):
        if prefix_user_tokens[i] != user_tokens[i]:
            return i
    return len(prefix_user_tokens)

all_logprobs = []
user_split_by_token = []
for i in range(len(USER_MESSAGE)):
    print(f"INFERENCED!, {i}/{len(USER_MESSAGE)}")
    user_split_by_token.append(USER_MESSAGE[i])
    prefix_user_tokens = llm.tokenize(USER_MESSAGE[:i+1].encode("utf-8"))
    common_prefix_length = get_common_prefix_length(prefix_user_tokens)
    llm.n_tokens = start_n_tokens + common_prefix_length
    llm.eval(prefix_user_tokens[common_prefix_length:])

    print(f"{start_n_tokens + common_prefix_length} -> {llm.n_tokens}")
    weight = 1.0
    for j in range(start_n_tokens + common_prefix_length-1, llm.n_tokens-1):
        logprobs = llm.logits_to_logprobs(llm.scores[j])
        weight *= math.exp(float(logprobs[prefix_user_tokens[j-start_n_tokens]]))
        print(f"P({repr(vocab[prefix_user_tokens[j-start_n_tokens]])}) = {float(logprobs[prefix_user_tokens[j-start_n_tokens]])}")

    logprobs = llm.logits_to_logprobs(llm.scores[llm.n_tokens-1])
    logprob = float(logprobs[BIG_SPLIT_TOKEN_INDEX])
    try:
        logprob = math.log(weight * math.exp(logprob))
    except ValueError:
        logprob = -20
    all_logprobs.append((BIG_SPLIT_TOKEN_INDEX, logprob))
    print(f"Common prefix: {[vocab[i] for i in user_tokens[:common_prefix_length][-5:]]}...")
    print(f"End: {[vocab[i] for i in prefix_user_tokens[-5:]]}")
    a0 = llm.logits_to_logprobs(llm.scores[llm.n_tokens-2])[BIG_SPLIT_TOKEN_INDEX]
    a1 = llm.logits_to_logprobs(llm.scores[llm.n_tokens-1])[BIG_SPLIT_TOKEN_INDEX]
    a2 = llm.logits_to_logprobs(llm.scores[llm.n_tokens-0])[BIG_SPLIT_TOKEN_INDEX]
    a3 = llm.logits_to_logprobs(llm.scores[llm.n_tokens+1])[BIG_SPLIT_TOKEN_INDEX]
    print(f"LogProb: {a0}, {a1}, {a2}, {a3}")
    print(f"WEIGHT: {weight}, BIGPROB: {math.exp(float(logprobs[BIG_SPLIT_TOKEN_INDEX]))}")
    print(f"Final Answer: {logprob}")

"""
user_split_by_token = []
for token in user_tokens:
    try:
        user_split_by_token.append(llm.detokenize([token]).decode("utf-8"))
    except UnicodeDecodeError:
        user_split_by_token.append("<COULD NOT DECODE>")
"""

"""
all_logprobs = []
for i in range(start_index, start_index+len(user_tokens)):
    logprobs = llm.logits_to_logprobs(llm.scores[i])
    top_100_indices = np.argsort(logprobs)[-100:][::-1]
    top_100_logprobs = [(int(i), float(logprobs[i])) for i in top_100_indices]
    all_logprobs.append(top_100_logprobs)
"""

print(all_logprobs[0])

open("result.json", "w").write(
    json.dumps({
        "split_tokens": [
            BIG_SPLIT_TOKEN,
            # SMALL_SPLIT_TOKEN,
        ],
        "vocab": vocab,
        "user_tokens": user_split_by_token,
        "all_logprobs": all_logprobs,
    }, indent=4)
)

def get_result():
    llm.load_state(root_state)
    llm.set_seed(random.randint(1000, 100000))
    max_tokens = 100

    tokens = []
    while len(tokens) < max_tokens:
        token = llm.sample(
            #temp=0.72 * (1.0 + 10.0 * math.exp(-len(tokens)-1)), # 0.72*(1+5*e^(-1))
            temp=0,
            top_k=40,
            top_p=0.95,
            repeat_penalty=1.1,
        )
        tokens.append(token)
        current_string = llm.detokenize(tokens).decode('utf-8')
        print("Current String:", current_string)

        if token == llm.token_eos():
            break
        llm.eval([token])

    return llm.detokenize(tokens).decode('utf-8')

def test_result():
    results_file = open("logs/results.log", "a")
    result = get_result()
    print("RESULT:", result)
    if result is not None:
        print("VALID!!!!")
        results_file.write(result + "\n")
        results_file.flush()
