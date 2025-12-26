import { Button, List, ListItem, ListItemText, Stack, Typography } from "@mui/material";

import { Artifact } from "../api";

interface ArtifactsListProps {
  artifacts?: Artifact[];
  onDownload: (artifact: Artifact) => Promise<void>;
}

export function ArtifactsList({ artifacts = [], onDownload }: ArtifactsListProps) {
  if (!artifacts.length) return null;
  return (
    <Stack spacing={1}>
      <Typography variant="h6">Artifacts</Typography>
      <List dense>
        {artifacts.map((artifact) => (
          <ListItem
            key={artifact.name}
            secondaryAction={
              <Button variant="outlined" onClick={() => onDownload(artifact)}>
                Download
              </Button>
            }
          >
            <ListItemText
              primary={artifact.name}
              secondary={`${artifact.contentType || "file"} • ${(artifact.sizeBytes / 1024).toFixed(1)} KB`}
            />
          </ListItem>
        ))}
      </List>
    </Stack>
  );
}
