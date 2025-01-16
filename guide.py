import os
import requests
import inquirer
import json
import subprocess
import yaml
import certifi
import urllib3
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from typing import Dict, List, Optional, Tuple

console = Console()

class BootcImageBuilder:
    def __init__(self):
        self.ollama_host = os.getenv('OLLAMA_HOST', 'http://192.168.10.220:11434')
        self.workspace_dir = "/workspace"

        # Configure urllib3 to use certifi's certificate bundle
        self.http = urllib3.PoolManager(
            cert_reqs='CERT_REQUIRED',
            ca_certs=certifi.where()
        )
    def get_models():
        try:
            response = requests.get('http://192.168.10.220:11434/api/ps')
            response.raise_for_status()
        
            data = response.json()
            return [model['name'].split(':')[0] for model in data.get('models', [])]
        except requests.exceptions.RequestException as e:
            print(f"Error fetching models: {e}")
            return []

    def select_model():
        models = get_models()
    
        if not models:
            print("No models available")
            return ""
    
        print("\nAvailable models:")
        for i, model in enumerate(models, 1):
            print(f"{i}. {model}")
    
        while True:
            try:
                choice = int(input("\nSelect a model (enter number): "))
                if 1 <= choice <= len(models):
                    USE_MODEL = models[choice - 1]
                    return USE_MODEL
                print("Invalid choice. Please try again.")
            except ValueError:
                print("Please enter a number.")

    def query_ollama(self, prompt: str) -> str:
        try:
            response = requests.post(
                f"{self.ollama_host}/api/generate",
                json={
                    "model": "codellama",
                    "prompt": prompt,
                    "stream": False
                },
                verify=certifi.where
            )
        except requests.exceptions.SSLError as ssl_err:
            console.print(f"[red]SSL Certificate Verification Failed: {ssl_err}")
            raise

        except requests.exceptions.RequestException as e:
            console.print(f"[red]Error connecting to Ollama: {e}")
            raise
            return response.json()['response']

    def run_command(self, cmd: str) -> Tuple[int, str, str]:
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate()
        return process.returncode, stdout, stderr

    def get_user_requirements(self) -> Dict:
        questions = [
            inquirer.List('base_image',
                         message="Select your base image",
                         choices=['registry.access.redhat.com/ubi9/ubi-minimal',
                                'registry.access.redhat.com/ubi9/ubi',
                                'Custom']),
            inquirer.Text('custom_image',
                         message="Enter your custom base image",
                         ignore=lambda x: x['base_image'] != 'Custom'),
            inquirer.Text('target_image',
                         message="Enter your target image name",
                         default='localhost/my-bootc-image:latest'),
            inquirer.Checkbox('features',
                             message="Select additional features to include",
                             choices=[
                                 'SSH Server',
                                 'System Tools',
                                 'Monitoring Tools',
                                 'Container Tools',
                                 'Development Tools'
                             ]),
            inquirer.Confirm('use_fips',
                           message="Enable FIPS mode?",
                           default=False),
            inquirer.Text('ostree_ref',
                         message="Enter OSTree ref name",
                         default='rhel/9/x86_64/custom'),
        ]
        
        return inquirer.prompt(questions)

    def generate_containerfile(self, requirements: Dict) -> str:
        prompt = f"""
        Create a Containerfile for a bootc image with these requirements:
        - Base image: {requirements['base_image'] if requirements['base_image'] != 'Custom' else requirements['custom_image']}
        - Features: {', '.join(requirements['features'])}
        - FIPS mode: {'enabled' if requirements.get('use_fips') else 'disabled'}
        - OSTree ref: {requirements['ostree_ref']}

        Requirements:
        1. Use bootc-specific instructions
        2. Include proper labels for RHEL UBI images
        3. Set up systemd appropriately
        4. Configure chosen features securely
        5. Follow RHEL best practices
        """
        
        containerfile = self.query_ollama(prompt)
        
        # Save Containerfile
        with open(os.path.join(self.workspace_dir, 'Containerfile'), 'w') as f:
            f.write(containerfile)
        return containerfile
        import subprocess
        subprocess.run(["vim", os.path.join(self.workspace_dir, 'Containerfile')])

    def build_image(self, target_image: str) -> bool:
        console.print("\n[yellow]Building image...[/yellow]")
        
        build_cmd = f"podman build -t {target_image} -f Containerfile ."
        returncode, stdout, stderr = self.run_command(build_cmd)
        
        if returncode == 0:
            console.print("\n[green]Build successful![/green]")
            
            # Get image details
            inspect_cmd = f"podman inspect {target_image}"
            _, inspect_output, _ = self.run_command(inspect_cmd)
            
            try:
                image_info = json.loads(inspect_output)[0]
                console.print("\n[blue]Image details:[/blue]")
                console.print(f"Size: {int(image_info.get('Size', 0)) / 1024 / 1024:.2f} MB")
                console.print(f"Created: {image_info.get('Created', 'Unknown')}")
                console.print(f"Architecture: {image_info.get('Architecture', 'Unknown')}")
            except (json.JSONDecodeError, IndexError):
                pass
            
            # Show usage instructions
            console.print(Panel.fit(
                f"[green]You can now use this image with:[/green]\n"
                f"bootc install {target_image}",
                title="Usage Instructions"
            ))
            return True
        else:
            console.print("\n[red]Build failed:[/red]")
            console.print(stderr)
            return False

def main():
    console.print(Panel.fit(
        "[blue]Welcome to the bootc Image Builder Guide![/blue]\n"
        "This tool will help you create a custom bootc image for RHEL 9",
        title="bootc Image Builder"
    ))
    
    builder = BootcImageBuilder()
    
    try:
        requirements = builder.get_user_requirements()
        
        console.print("\n[yellow]Generating Containerfile...[/yellow]")
        containerfile = builder.generate_containerfile(requirements)
        
        console.print("\n[blue]Generated Containerfile:[/blue]")
        console.print(Markdown(f"```dockerfile\n{containerfile}\n```"))
        
        if inquirer.confirm("Would you like to build the image now?"):
            builder.build_image(requirements['target_image'])
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Build process cancelled by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error: {str(e)}[/red]")

if __name__ == "__main__":
    main()
