# **Your Text, Your Style – Auto-Generate a Presentation**

Create a publicly accessible web app that lets anyone turn bulk text, markdown, or prose into a fully formatted PowerPoint presentation that matches their chosen template’s look and feel.

---

## **Objective**

Your app should allow users to:

* Paste a large chunk of text (can be markdown or long-form prose)  
* Optionally enter a one-line guidance for the tone, structure, or use case (e.g.: “turn into an investor pitch deck”)  
* Provide their LLM API key of choice (e.g. OpenAI, Anthropic, Gemini)  
* Upload a PowerPoint template or presentation (.pptx or .potx)

The app then:

* Analyzes and breaks down the input text into slide content and structure  
* Infers and applies the style, colors, fonts, and images from the uploaded PowerPoint file to the generated slides  
* Reuses images found in the uploaded template/presentation where appropriate  
* Generates and outputs a new .pptx file for user download—without generating new images using AI

---

## **Requirements**

Users must be able to:

* Paste or type a large block of text  
* Enter their own LLM API key (never stored or logged)  
* Upload a PowerPoint template or presentation file (.pptx/.potx)  
* Download the newly generated presentation

App must:

* Map and split the input text intelligently into slide contents (not just “fixed 3 slides”)  
* Copy the uploaded template’s style and layout as much as possible (including images, layouts, colors, fonts)  
* Choose a reasonable number of slides, based on the text and optional guidance  
* Support any LLM provider, using API calls with user-supplied key  
* Be published in a public GitHub repository (with MIT License and full README)

---

## **Optional Enhancements (Not Required – For Extra Credit)**

* Auto-generate speaker notes for each slide (via LLM)  
* Support various tones/stylistic modes (e.g. professional, investor pitch, visual-heavy, technical)  
* Provide slide previews before download  
* Offer common-use-case guidance templates (“Sales deck”, “Research summary”, etc.)  
* Add robust error handling, file size/upload limits, and API retry logic

---

## **Deliverables**

1. Public GitHub repository containing:  
   * Full front-end (and back-end, if needed) code  
   * MIT License  
   * README with setup and usage instructions  
2. Working hosted link (demo app)  
3. Short write-up (200–300 words) explaining:  
   * How the input text is parsed and mapped to slides  
   * How your app applies the visual style and assets of the template

---

## 

## 

## 

## **Evaluation Criteria (3 Marks)**

| Criteria | Marks |
| :---- | :---- |
| Output functionality | 1.5 |
| Code quality & clarity | 1.0 |
| UI/UX polish & extras | 0.5 |

---

## **Notes**

* You may use any programming stack (Python, JS, etc.)  
* You may apply reasonable technical limits (e.g., file size)  
* Only reuse images from the template file; do not create/generate images via AI  
* Inferring precise layout details is NOT required—do the best you can  
* Do not store or log any sensitive user input, especially API keys

