import os
import site


def set_pth():
    # Step 1: Get the absolute path of the current project
    project_root = os.path.abspath(os.path.dirname(__file__))

    # Define the content for the .pth file dynamically
    pth_content = f"import site;site.addsitedir('{project_root}', set());\n"

    # Step 2: Write the .pth file to the site-packages directory
    # Get the site-packages directories
    site_packages = site.getsitepackages()

    # Path where the .pth file will go (using the first site-packages directory)
    pth_file_path = os.path.join(site_packages[0], f"voiceagent.pth")

    # Write the .pth file to the correct location
    with open(pth_file_path, "w") as f:
        f.write(pth_content)

    print(f"Created {pth_file_path} with project root: {project_root}")


if __name__ == "__main__":
    set_pth()
