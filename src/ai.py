import openai
import os

openai.api_key = os.getenv("OPENAI_API_KEY")

model = "gpt-4"

prompt_system = """The following is text from a page of school notes. 
Your job is to determine the subject, or topic, of the notes. 
Once you know the subject, you should provide suggestions to help the author better prepare for an exam on the topic. 
Be sure to highlight areas which can be commonly misunderstood. Pretend you are a medical school professor.
Your goal is to help someone study as effectively as possible.
Ignore any typos or grammatical errors, as the scanned text is not perfect. 
You should focus on substantive, factual errors. Do not worry about formatting, grammar, or misspellings.
Be as technical and specific as possible. Try to avoid study points which go beyond the scope covered in the notes provided.
Provide the response in an easy-to-read, actionable format. If applicable, include some sample questions which could be asked on the exam. Where possible, make them multiple choice.
Format your response using markdown with the Subject in a larger size."""

def get_commentary(notes: str):
    response = openai.ChatCompletion.create(
        model=model,
        messages=[{"content": prompt_system, "role": "system"},
                  {"content": notes, "role": "user"}],
    )
    return response.choices[0].message.content

def main():
    input = """Paragraph:
- HDL can extract cholesterol + chol. esters form cell membrane and return to liver
3) LDL - recomended levels depend on risk of heart disease <100 mg /dl @ risk for heart disease <70 mg/dl w/ heart disease | diabetes 100-120 mg/dl no diagnosed heart disease
ILDL=1 of CV disease and stroke, promotes build up of fatty deposits w/ in arteries reducing or blocking blood flow and O2 delivery 1 risk because oxidation of protein and lipid contents of LDL particles
Cholesterol, ano. esters, and tats are
absorbed in small intestine and assembled into Chilomicrons
1) chylomicrons are assembled in intestine and contain a po B48
2) released into lymph
3) acquire apo CHI and aro E from HDL in plasma
4) lipoprotein lipase on surface of non-hepatic tissues, hydrolyzes triglycerides
5) remnants depleted of glycerol and
FFA transfer apo C-I Back to HDL 4) remnants w/apDE and ato B48 bind to apoE receptor on livercks,
resulting in op tave of remnants
"""

    print(get_commentary(input))

if __name__ == "__main__":
    main()
