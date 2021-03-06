# -*- coding: utf-8 -*-
"""gpt-neo-ner.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1Sg_atC2P8GHgXnIGQIsvt8Y3YisgW3b_
"""



from transformers import TFAutoModelForTokenClassification, AutoTokenizer,GPT2Tokenizer, GPTNeoModel
import tensorflow as tf
from datasets import load_dataset, load_metric

"""# Chargement du jeu de données"""

datasets = load_dataset("conll2003")

datasets["train"][0]

"""# Chargement du modele"""

tokenizer = AutoTokenizer.from_pretrained('EleutherAI/gpt-neo-1.3B', add_prefix_space=True)

def tokenize_and_align_labels(examples):
  
  tokenized_inputs = tokenizer(examples["tokens"], truncation=True, is_split_into_words=True)
  labels=[]

  for phrase_token, tags in zip(examples["tokens"],examples["ner_tags"]):

    label=[]


    tokenized=tokenizer(phrase_token,is_split_into_words=True)

    words_ids=tokenized.word_ids()

    for id in words_ids:
      label.append(tags[id])
    
    labels.append(label)
  
  tokenized_inputs["labels"]=labels
  return tokenized_inputs



examples=datasets['train'][:5]

print(tokenize_and_align_labels(examples))

tokenized_datasets = datasets.map(tokenize_and_align_labels, batched=True)

print(datasets)
print(tokenized_datasets)

"""# Label"""

label_list = [
    "O",       # Outside of a named entity
    "B-MISC",  # Beginning of a miscellaneous entity right after another miscellaneous entity
    "I-MISC",  # Miscellaneous entity
    "B-PER",   # Beginning of a person's name right after another person's name
    "I-PER",   # Person's name
    "B-ORG",   # Beginning of an organisation right after another organisation
    "I-ORG",   # Organisation
    "B-LOC",   # Beginning of a location right after another location
    "I-LOC"    # Location
]

sequence = "Hugging Face Inc. is a company based in New York City. Its headquarters are in DUMBO, therefore very" \
           "close to the Manhattan Bridge."

# Bit of a hack to get the tokens with the special tokens
tokens = tokenizer.tokenize(tokenizer.decode(tokenizer.encode(sequence)))
inputs = tokenizer.encode(sequence, return_tensors="tf")

tokenizer.decode(inputs[0])
tokens

"""# Token classification for GPT-NEO"""

from transformers import PreTrainedModel

import torch as T

import torch.nn as nn

class TokenClassificationForGPT(nn.Module):
    def __init__(self, hidden_size: int, num_labels:int, gpt_model_name:str):
        super(TokenClassificationForGPT,self).__init__()
        self.num_labels=num_labels
        self.gptneo = GPTNeoModel.from_pretrained(gpt_model_name)
        self.fc1 = nn.Linear(hidden_size, num_labels)
        
    def forward(self,input_ids=None,attention_mask=None,token_type_ids=None,position_ids=None,head_mask=None,inputs_embeds=None,labels=None,output_attentions=None,output_hidden_states=None,return_dict=None):

        outputs = self.gptneo(input_ids)

        logits  = self.fc1(outputs[0]) 
        loss = None
        if labels is not None:
            loss_fct = nn.CrossEntropyLoss()
            # Only keep active parts of the loss
            if attention_mask is not None:
                active_loss = attention_mask.view(-1) == 1
                active_logits = logits.view(-1, self.num_labels)
                active_labels = T.where(
                    active_loss, labels.view(-1), T.tensor(loss_fct.ignore_index).type_as(labels)
                )
                loss = loss_fct(active_logits, active_labels)
            else:
                loss = loss_fct(logits.view(-1, self.num_labels), labels.view(-1))

    
        output = (logits,) + outputs[2:]
        return ((loss,) + output) if loss is not None else output

from transformers import AutoModelForTokenClassification, TrainingArguments, Trainer,GPTNeoConfig


model = TokenClassificationForGPT(gpt_model_name="EleutherAI/gpt-neo-1.3B",num_labels=len(label_list),hidden_size=2048)

metric = load_metric("seqeval")

def compute_metrics(p):
    predictions, labels = p
    predictions = np.argmax(predictions, axis=2)

    # Remove ignored index (special tokens)
    true_predictions = [
        [label_list[p] for (p, l) in zip(prediction, label) if l != -100]
        for prediction, label in zip(predictions, labels)
    ]
    true_labels = [
        [label_list[l] for (p, l) in zip(prediction, label) if l != -100]
        for prediction, label in zip(predictions, labels)
    ]

    results = metric.compute(predictions=true_predictions, references=true_labels)
    return {
        "precision": results["overall_precision"],
        "recall": results["overall_recall"],
        "f1": results["overall_f1"],
        "accuracy": results["overall_accuracy"],
    }

"""# Model training"""

from transformers import DataCollatorForTokenClassification

data_collator = DataCollatorForTokenClassification(tokenizer)

small_tokenized_datasets_train=tokenized_datasets["train"].select(range(100))
small_tokenized_datasets_validation=tokenized_datasets["validation"].select(range(100))

type(tokenized_datasets["train"])

type(small_tokenized_datasets)

tokenizer

tokenizer.pad_token = -100

batch_size = 32
args = TrainingArguments(
    "test-ner",
    evaluation_strategy = "epoch",
    learning_rate=2e-4,
    per_device_train_batch_size=batch_size,
    per_device_eval_batch_size=batch_size,
    num_train_epochs=1,
    weight_decay=0.01,
)

trainer = Trainer(
    model,
    args,
    train_dataset=small_tokenized_datasets,
    eval_dataset=small_tokenized_datasets_validation,
    data_collator=data_collator,
    tokenizer=tokenizer,
    compute_metrics=compute_metrics
)

trainer.train()
