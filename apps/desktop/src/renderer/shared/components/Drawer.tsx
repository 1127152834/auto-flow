import { Modal, type ModalProps } from './Modal'
/** Side placement shares the modal's busy guard, scroll body and focus restoration. */
export function Drawer(props: Omit<ModalProps, 'placement'>) { return <Modal {...props} placement="drawer" /> }
