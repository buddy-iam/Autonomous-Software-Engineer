from github import Github, Auth
import uuid

def push_to_github(token: str, repo_name: str, code_output: dict) -> str:
    """Creates a repo, branches, commits code, and opens a PR. Returns the PR URL."""
    try:
        g = Github(auth=Auth.Token(token))
        user = g.get_user()
        
        try:
            repo = user.get_repo(repo_name)
        except:
            repo = user.create_repo(name=repo_name, private=True, auto_init=True)
            
        branch_name = f"ai-update-{str(uuid.uuid4())[:8]}"
        
        try:
            main_branch = repo.get_branch("main")
        except:
            main_branch = repo.get_branch("master")
            
        repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=main_branch.commit.sha)
        
        for file_path, content in code_output.items():
            try:
                contents = repo.get_contents(file_path, ref=branch_name)
                repo.update_file(contents.path, "AI Agent Update", content, contents.sha, branch=branch_name)
            except:
                repo.create_file(file_path, "AI Agent Initial Commit", content, branch=branch_name)
                
        pr = repo.create_pull(
            title="AI Swarm Code Update", 
            body="Automated optimization and feature addition by Autonomous Agency.", 
            head=branch_name, 
            base=main_branch.name
        )
        return pr.html_url
    except Exception as e:
        print(f"GitHub Execution Error: {e}")
        return None