import os
import openai
import base64

# --- Configuration ---
# Ensure these environment variables are set before running the script
MY_API_KEY = os.getenv("my_api_key")
MY_BASE_URL = os.getenv("my_base_url")
MY_MODEL = os.getenv("my_model", "gpt-5-mini-2025-08-07")

# --- Local Image Path ---
# The path to the image you want to process
IMAGE_PATH = "/Users/chenboyu/Desktop/Epoch_Drift_Benchmark/google_som_marked.png"

def encode_image_from_path(image_path):
    """Reads an image file and encodes it to a base64 string."""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    except FileNotFoundError:
        print(f"Error: The file was not found at the specified path: {image_path}")
        return None
    except Exception as e:
        print(f"An error occurred while reading the file: {e}")
        return None

def main():
    """Main function to run the API test."""
    # --- 1. Initialization and validation ---
    if not all([MY_API_KEY, MY_BASE_URL, MY_MODEL]):
        print("Error: One or more environment variables (my_api_key, my_base_url, my_model) are not set.")
        return

    try:
        client = openai.OpenAI(
            api_key=MY_API_KEY,
            base_url=MY_BASE_URL,
        )
        print("OpenAI client initialized successfully.")
    except Exception as e:
        print(f"Error initializing OpenAI client: {e}")
        return

    # --- 2. Encode the local image ---
    print(f"Reading and encoding image from: {IMAGE_PATH}")
    base64_image = encode_image_from_path(IMAGE_PATH)

    if not base64_image:
        print("Halting script because image could not be encoded.")
        return

    print("Image encoded successfully.")

    # --- 3. Send request to the API ---
    try:
        print(f"\nSending request to model '{MY_MODEL}' with the local image...")
        response = client.chat.completions.create(
            model=MY_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        # You can customize your question here
                        {"type": "text", "text": "Describe this image in detail. What does it show?"},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}},
                    ],
                }
            ],
            max_tokens=2500, # Increased max_tokens for a potentially more detailed description
        )

        # --- 4. Process and display the response ---
        print("\n--- Raw API Response ---")
        print(response)
        print("------------------------")

        if response.choices:
            print("\n--- Parsed API Message ---")
            print(response.choices[0].message.content)
            print("--------------------------")
        else:
            print("\n--- Analysis ---")
            print("The API returned a valid but empty response. No choices were provided.")
            print("----------------")

    except openai.APIConnectionError as e:
        print(f"\nFailed to connect to the API: {e}")
        print("Please check your network connection and the 'my_base_url' variable.")
    except openai.APIStatusError as e:
        print(f"\nAPI returned an error (Status {e.status_code}): {e.response}")
        print("Please check your API key, model name, and account status.")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
