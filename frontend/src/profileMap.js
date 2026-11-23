export function postsForChip(posts, chip) {
  if (chip === "drafts") return posts.filter((post) => post.status === "draft");
  if (chip === "all") return posts.filter((post) => post.status !== "draft");
  return posts.filter((post) => post.category === chip && post.status !== "draft");
}

export function canOpenProfileMap(posts, chip) {
  return postsForChip(posts, chip).length > 0;
}
