import { redirect } from 'next/navigation';

interface Props {
  params: { locale: string; id: string };
}

export default function PatientDetailPage({ params }: Props) {
  redirect(`/${params.locale}/patients/${params.id}/overview`);
}
