import { useParams } from "react-router-dom";

export default function RepoIllustrationPage() {
  const { repoId } = useParams();

  return (
    <div className="min-h-screen flex items-center justify-center text-white">
      <h1>Illustration for: {repoId}</h1>
      {/*insights htb2a hna*/}
    </div>
  );
}