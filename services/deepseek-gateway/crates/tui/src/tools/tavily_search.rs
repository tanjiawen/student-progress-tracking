//! Tavily web search tool - replaces DuckDuckGo/Bing with AI-optimized search.

use async_trait::async_trait;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::time::Duration;

use super::spec::{
    ApprovalRequirement, ToolCapability, ToolContext, ToolError, ToolResult, ToolSpec,
    
};
use crate::network_policy::{Decision, NetworkPolicyDecider};

const TAVILY_HOST: &str = "api.tavily.com";
const DEFAULT_MAX_RESULTS: usize = 5;
const MAX_RESULTS: usize = 10;

/// Check network policy for the given host.
fn check_policy(decider: Option<&NetworkPolicyDecider>, host: &str) -> Result<(), ToolError> {
    let Some(decider) = decider else {
        return Ok(());
    };
    match decider.evaluate(host, "web_search") {
        Decision::Allow => Ok(()),
        Decision::Deny => Err(ToolError::permission_denied(format!(
            "web search to '{host}' blocked by network policy"
        ))),
        Decision::Prompt => Err(ToolError::permission_denied(format!(
            "web search to '{host}' requires approval; \
             re-run after `/network allow {host}` or set network.default = \"allow\" in config"
        ))),
    }
}

// ============================================
// Data structures
// ============================================

#[derive(Debug, Clone, Serialize, Deserialize)]
struct TavilyResponse {
    results: Vec<TavilySearchEntry>,
    #[serde(default)]
    response_metadata: Option<ResponseMetadata>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct TavilySearchEntry {
    title: String,
    url: String,
    content: String,
    #[serde(default)]
    published_date: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct ResponseMetadata {
    query: String,
    #[serde(default)]
    answer: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
struct WebSearchResponse {
    query: String,
    source: String,
    count: usize,
    message: String,
    results: Vec<WebSearchEntry>,
    #[serde(skip_serializing_if = "Option::is_none")]
    answer: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
struct WebSearchEntry {
    title: String,
    url: String,
    snippet: Option<String>,
}

// ============================================
// Helper functions for query extraction
// ============================================

/// Extract search query from input, supporting multiple formats:
/// - `query` field (primary)
/// - `q` field (compatibility alias)
/// - `search_query[0].q` or `search_query[0].query` (array form)
fn extract_search_query(input: &Value) -> Result<String, ToolError> {
    // Try primary query field
    for key in ["query", "q"] {
        if let Some(value) = input.get(key) {
            if let Some(query) = value.as_str() {
                let query = query.trim();
                if !query.is_empty() {
                    return Ok(query.to_string());
                }
            }
        }
    }

    // Try array form: search_query[0].q or search_query[0].query
    if let Some(items) = input.get("search_query").and_then(|v| v.as_array()) {
        if let Some(first) = items.first() {
            for key in ["q", "query"] {
                if let Some(value) = first.get(key) {
                    if let Some(query) = value.as_str() {
                        let query = query.trim();
                        if !query.is_empty() {
                            return Ok(query.to_string());
                        }
                    }
                }
            }
        }
    }

    Err(ToolError::missing_field("query"))
}

/// Extract optional max_results from input, supporting array form.
fn extract_max_results(input: &Value) -> u64 {
    // Direct field
    if let Some(value) = input.get("max_results").and_then(|v| v.as_u64()) {
        return value;
    }
    // Array form: search_query[0].max_results
    if let Some(items) = input.get("search_query").and_then(|v| v.as_array()) {
        if let Some(first) = items.first() {
            if let Some(value) = first.get("max_results").and_then(|v| v.as_u64()) {
                return value;
            }
        }
    }
    DEFAULT_MAX_RESULTS as u64
}

// ============================================
// Tool implementation
// ============================================

pub struct TavilySearchTool {
    client: Client,
    api_key: String,
}

impl TavilySearchTool {
    /// Create a new TavilySearchTool with the given API key.
    pub fn new(api_key: String) -> Self {
        let client = Client::builder()
            .timeout(Duration::from_secs(30))
            .build()
            .expect("Failed to create HTTP client");
        Self { client, api_key }
    }

    /// Perform the actual Tavily API search.
    async fn tavily_search(
        &self,
        query: &str,
        max_results: usize,
    ) -> Result<TavilyResponse, ToolError> {
        let request_body = json!({
            "api_key": self.api_key,
            "query": query,
            "search_depth": "advanced",
            "max_results": max_results,
            "include_answer": true,
            "include_raw_content": false,
            "include_domains": [],
            "exclude_domains": []
        });

        let resp = self
            .client
            .post("https://api.tavily.com/search")
            .header("Content-Type", "application/json")
            .json(&request_body)
            .send()
            .await
            .map_err(|e| ToolError::execution_failed(format!("Tavily request failed: {e}")))?;

        let status = resp.status();
        if !status.is_success() {
            return Err(ToolError::execution_failed(format!(
                "Tavily API failed: HTTP {}",
                status.as_u16()
            )));
        }

        resp.json::<TavilyResponse>()
            .await
            .map_err(|e| ToolError::execution_failed(format!("Failed to parse Tavily response: {e}")))
    }

    /// Format the Tavily response into the standard web search response format.
    fn format_response(&self, tavily: TavilyResponse, query: &str) -> WebSearchResponse {
        let results: Vec<WebSearchEntry> = tavily
            .results
            .into_iter()
            .take(MAX_RESULTS)
            .map(|r| WebSearchEntry {
                title: r.title,
                url: r.url,
                snippet: Some(r.content),
            })
            .collect();

        let count = results.len();
        let message = if count == 0 {
            "No results found".to_string()
        } else {
            format!("Found {} result(s)", count)
        };

        // Extract AI-generated answer from Tavily response
        let answer = tavily
            .response_metadata
            .as_ref()
            .and_then(|m| m.answer.clone())
            .filter(|a| !a.is_empty());

        WebSearchResponse {
            query: query.to_string(),
            source: "tavily".to_string(),
            count,
            message,
            results,
            answer,
        }
    }
}

#[async_trait]
impl ToolSpec for TavilySearchTool {
    fn name(&self) -> &'static str {
        "web_search" // Keep the same name for compatibility
    }

    fn description(&self) -> &'static str {
        "Search the web using Tavily API - optimized for AI applications with intelligent filtering and context-aware results"
    }

    fn input_schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query."
                },
                "q": {
                    "type": "string",
                    "description": "Search query (compatibility alias)."
                },
                "search_query": {
                    "type": "array",
                    "description": "Array form for advanced queries: [{\"q\":\"...\", \"max_results\": 5}]",
                    "items": {
                        "type": "object",
                        "properties": {
                            "q": { "type": "string" },
                            "query": { "type": "string" },
                            "max_results": { "type": "integer" }
                        }
                    }
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 5, max: 10)"
                },
                "timeout_ms": {
                    "type": "integer",
                    "description": "Timeout in milliseconds (default: 15000, max: 60000)"
                }
            },
            "required": ["query"]
        })
    }

    fn capabilities(&self) -> Vec<ToolCapability> {
        vec![ToolCapability::ReadOnly, ToolCapability::Network]
    }

    fn approval_requirement(&self) -> ApprovalRequirement {
        ApprovalRequirement::Auto
    }

    async fn execute(&self, input: Value, context: &ToolContext) -> Result<ToolResult, ToolError> {
        let query = extract_search_query(&input)?;
        if query.is_empty() {
            return Err(ToolError::invalid_input("Query cannot be empty"));
        }

        let max_results = extract_max_results(&input) as usize;
        let max_results = max_results.clamp(1, MAX_RESULTS);

        // Check network policy
        let decider = context.network_policy.as_ref();
        check_policy(decider, TAVILY_HOST)?;

        // Perform the search
        let response = self.tavily_search(&query, max_results).await?;
        let formatted = self.format_response(response, &query);

        ToolResult::json(&formatted)
            .map_err(|e| ToolError::execution_failed(e.to_string()))
    }
}

// ============================================
// Tests
// ============================================

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_extract_search_query_with_query_field() {
        let input = json!({"query": "test search"});
        let result = extract_search_query(&input).unwrap();
        assert_eq!(result, "test search");
    }

    #[test]
    fn test_extract_search_query_with_q_field() {
        let input = json!({"q": "test search via q"});
        let result = extract_search_query(&input).unwrap();
        assert_eq!(result, "test search via q");
    }

    #[test]
    fn test_extract_search_query_with_search_query_array() {
        let input = json!({"search_query": [{"q": "array search"}]});
        let result = extract_search_query(&input).unwrap();
        assert_eq!(result, "array search");
    }

    #[test]
    fn test_extract_search_query_prefers_query_over_q() {
        let input = json!({"query": "primary", "q": "secondary"});
        let result = extract_search_query(&input).unwrap();
        assert_eq!(result, "primary");
    }

    #[test]
    fn test_extract_search_query_missing_returns_error() {
        let input = json!({"max_results": 5});
        let result = extract_search_query(&input);
        assert!(result.is_err());
    }

    #[test]
    fn test_extract_max_results_direct() {
        let input = json!({"max_results": 8});
        assert_eq!(extract_max_results(&input), 8);
    }

    #[test]
    fn test_extract_max_results_from_array() {
        let input = json!({"search_query": [{"max_results": 3}]});
        assert_eq!(extract_max_results(&input), 3);
    }

    #[test]
    fn test_extract_max_results_default() {
        let input = json!({});
        assert_eq!(extract_max_results(&input), DEFAULT_MAX_RESULTS as u64);
    }

    #[test]
    fn test_input_schema_has_required_query() {
        let tool = TavilySearchTool::new("test-key".to_string());
        let schema = tool.input_schema();

        let query_schema = schema.pointer("/properties/query").expect("query property should exist");
        assert_eq!(query_schema.pointer("/type").expect("type should exist").as_str().unwrap(), "string");

        let required = schema.pointer("/required").expect("required should exist");
        let required_array: Vec<&str> = required.as_array()
            .unwrap()
            .iter()
            .filter_map(|v| v.as_str())
            .collect();
        assert!(required_array.contains(&"query"));
    }

    #[test]
    fn test_input_schema_has_q_compatibility() {
        let tool = TavilySearchTool::new("test-key".to_string());
        let schema = tool.input_schema();

        let q_schema = schema.pointer("/properties/q");
        assert!(q_schema.is_some(), "q property should exist for compatibility");
    }

    #[test]
    fn test_input_schema_has_search_query_array() {
        let tool = TavilySearchTool::new("test-key".to_string());
        let schema = tool.input_schema();

        let sq_schema = schema.pointer("/properties/search_query");
        assert!(sq_schema.is_some(), "search_query property should exist for compatibility");
    }

    #[test]
    fn test_tool_name_is_web_search() {
        let tool = TavilySearchTool::new("test-key".to_string());
        assert_eq!(tool.name(), "web_search");
    }

    #[test]
    fn test_capabilities() {
        let tool = TavilySearchTool::new("test-key".to_string());
        let caps = tool.capabilities();
        assert!(caps.contains(&ToolCapability::ReadOnly));
        assert!(caps.contains(&ToolCapability::Network));
    }
}
