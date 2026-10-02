import React, { useState, useEffect } from 'react';
import { Send, Paperclip, Settings, FileCode, Github, Loader2, Check, RefreshCw } from 'lucide-react';

export default function AIAgencyUI() {
  const [threadId, setThreadId] = useState("");
  const [prompt, setPrompt] = useState("");
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  
  // App State
  const [isPaused, setIsPaused] = useState(false);
  const [plan, setPlan] = useState("");
  const [codeFiles, setCodeFiles] = useState(null);
  const [githubUrl, setGithubUrl] = useState("");
  
  // Settings (Stored locally)
  const [backendUrl, setBackendUrl] = useState("https://your-tunnel.trycloudflare.com");
  const [githubToken, setGithubToken] = useState("");
  const [githubRepo, setGithubRepo] = useState("");

  useEffect(() => {
    resetSession();
  }, []);

  const resetSession = () => {
    setThreadId(Math.random().toString(36).substring(7)); // New Memory Thread
    setIsPaused(false);
    setPlan("");
    setCodeFiles(null);
    setGithubUrl("");
    setPrompt("");
    setFiles([]);
  };

  const callBackend = async (action, overridePrompt = prompt) => {
    setLoading(true);
    const formData = new FormData();
    formData.append("thread_id", threadId);
    formData.append("action", action);
    if (overridePrompt) formData.append("prompt", overridePrompt);
    if (githubToken) formData.append("github_token", githubToken);
    if (githubRepo) formData.append("github_repo", githubRepo);
    files.forEach(f => formData.append("files", f));

    try {
      const res = await fetch(`${backendUrl}/api/chat`, { 
        method: "POST", 
        body: formData 
      });
      const data = await res.json();
      
      setIsPaused(data.is_paused);
      setPlan(data.plan);
      if (data.code_files && Object.keys(data.code_files).length > 0) setCodeFiles(data.code_files);
      setGithubUrl(data.github_url);
      setPrompt("");
      setFiles([]);
    } catch (err) {
      alert("Error connecting to backend. Ensure your Cloudflared URL is correct and the FastAPI server is running.");
    }
    setLoading(false);
  };

  const handleStart = () => callBackend("start");
  const handleApprove = () => callBackend("approve", "");
  const handleFeedback = () => callBackend("feedback");

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col items-center py-10 px-4">
      <div className="w-full max-w-4xl bg-gray-900 rounded-xl shadow-2xl overflow-hidden border border-gray-800">
        
        {/* Header */}
        <div className="flex justify-between items-center p-4 border-b border-gray-800 bg-gray-900">
          <h1 className="text-xl font-bold flex items-center gap-2">
            <FileCode className="text-blue-500" /> Autonomous Agency
          </h1>
          <div className="flex gap-2">
            <button onClick={resetSession} className="p-2 hover:bg-gray-800 rounded flex items-center gap-2 text-sm text-gray-400">
              <RefreshCw className="w-4 h-4" /> New Session
            </button>
            <button onClick={() => setShowSettings(!showSettings)} className="p-2 hover:bg-gray-800 rounded text-gray-400">
              <Settings className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Settings Dropdown */}
        {showSettings && (
          <div className="p-4 bg-gray-800 border-b border-gray-700 space-y-4">
             <div>
              <label className="text-xs text-gray-400">Cloudflared Backend URL</label>
              <input type="text" className="w-full p-2 mt-1 bg-gray-900 rounded border border-gray-700 text-sm outline-none" value={backendUrl} onChange={(e) => setBackendUrl(e.target.value)} />
            </div>
            <div className="flex gap-4">
              <div className="flex-1">
                <label className="text-xs text-gray-400">GitHub PAT (Optional)</label>
                <input type="password" className="w-full p-2 mt-1 bg-gray-900 rounded border border-gray-700 text-sm outline-none" value={githubToken} onChange={(e) => setGithubToken(e.target.value)} />
              </div>
              <div className="flex-1">
                <label className="text-xs text-gray-400">Target Repository</label>
                <input type="text" placeholder="e.g., my-awesome-app" className="w-full p-2 mt-1 bg-gray-900 rounded border border-gray-700 text-sm outline-none" value={githubRepo} onChange={(e) => setGithubRepo(e.target.value)} />
              </div>
            </div>
          </div>
        )}

        {/* View Area */}
        <div className="h-[500px] p-6 overflow-y-auto bg-gray-950/50">
          {loading ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-400 space-y-4">
              <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
              <p>Agency Swarm is working...</p>
            </div>
          ) : (
            <div className="space-y-6">
              
              {/* Plan Output */}
              {plan && (
                <div className="p-4 bg-gray-800 rounded border border-gray-700">
                  <h3 className="text-blue-400 font-semibold mb-2">Project Manager's Blueprint</h3>
                  <pre className="whitespace-pre-wrap text-sm text-gray-300 font-sans">{plan}</pre>
                </div>
              )}

              {/* Final Code Output */}
              {codeFiles && (
                <div className="p-4 bg-green-900/20 border border-green-800/50 rounded">
                  <h3 className="text-green-400 font-semibold mb-4">Final Optimized Code</h3>
                  {githubUrl && (
                    <a href={githubUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 text-sm bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded mb-4 transition">
                      <Github className="w-4 h-4" /> View Pull Request on GitHub
                    </a>
                  )}
                  {Object.entries(codeFiles).map(([filename, code]) => (
                    <div key={filename} className="mb-4">
                      <p className="text-xs text-gray-400 bg-gray-900 p-2 rounded-t font-mono border border-gray-800 border-b-0">{filename}</p>
                      <pre className="bg-gray-950 p-4 rounded-b text-xs text-gray-300 overflow-x-auto border border-gray-800">{code}</pre>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Input Controls */}
        <div className="p-4 bg-gray-900 border-t border-gray-800">
          
          {/* HITL Approval State */}
          {isPaused && !loading && (
            <div className="mb-4 p-3 bg-blue-900/30 border border-blue-800 rounded-lg flex items-center justify-between">
              <span className="text-sm text-blue-200">The Project Manager is waiting for your approval.</span>
              <button onClick={handleApprove} className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded text-sm transition">
                <Check className="w-4 h-4" /> Approve & Build
              </button>
            </div>
          )}

          {files.length > 0 && (
            <div className="flex gap-2 mb-3 overflow-x-auto">
              {files.map((file, i) => (
                <span key={i} className="text-xs bg-gray-800 px-3 py-1 rounded-full border border-gray-700">{file.name}</span>
              ))}
            </div>
          )}
          
          <div className="flex gap-2">
            <label className="p-3 bg-gray-800 hover:bg-gray-700 rounded-lg cursor-pointer transition border border-gray-700">
              <Paperclip className="w-5 h-5 text-gray-400" />
              <input type="file" multiple onChange={(e) => setFiles([...files, ...Array.from(e.target.files)])} className="hidden" />
            </label>
            
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder={isPaused ? "Request changes to the plan..." : "Describe the feature or project to build..."}
              className="flex-1 bg-gray-950 p-3 rounded-lg border border-gray-700 resize-none outline-none focus:border-blue-500 text-sm"
              rows={2}
            />
            
            <button 
              onClick={isPaused ? handleFeedback : handleStart}
              disabled={!prompt || loading}
              className="p-3 bg-white text-gray-900 hover:bg-gray-200 disabled:opacity-50 rounded-lg transition flex items-center justify-center w-12"
            >
              <Send className="w-5 h-5" />
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}